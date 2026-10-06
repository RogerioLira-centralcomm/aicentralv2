import React, {useEffect, useMemo, useState} from 'react';
import {Icon} from './Icon';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {SidebarAccount, useCreditUsage} from './SidebarAccount';
import {entityHref, entityIdentity, entityLabel, groupWorkspaceProjects} from '../workspaceEntities.mjs';
import {workspaceUserPhoto} from '../workspaceIdentity.mjs';
import {workspaceSolutionItems} from '../workspaceSolutions';

// The context rail owns Workspace navigation and project-specific content.
// One order across Workspace and Chat: start, conversations, then brand → project.
// Account lives in the footer with the person's photo and credit use, as in Reports.
const HOME_ITEMS = [
  {id: 'home', label: 'Início', key: 'home', icon: 'home'},
  {id: 'conversas', label: 'Conversas', key: 'conversations', icon: 'compose'},
  {id: 'marcas', label: 'Marcas', key: 'brands', icon: 'brand'},
  {id: 'projetos', label: 'Projetos', key: 'projects', icon: 'folder'},
];
const MOBILE_HOME_ITEMS = HOME_ITEMS;

function readCollapsed(mode, preferenceKey) {
  try {
    if (mode === 'home' && window.matchMedia('(max-width: 760px)').matches) return true;
    const saved = window.localStorage.getItem(`cadu:sidebar:${preferenceKey}`);
    return mode === 'home' ? saved !== 'open' : saved === 'collapsed';
  } catch (_) { return mode === 'home'; }
}

const AVATAR_BADGES = ['badge-comet.png', 'badge-ribbon.png', 'badge-orbit.png', 'badge-prism.png', 'badge-sunburst.png', 'badge-sphere.png'];
function avatarBadgeSource(user = {}) {
  const configured = String(user.avatarBadge || '').trim();
  const seed = Array.from(String(user.name || '')).reduce((total, character) => total + character.charCodeAt(0), 0);
  return `/static/images/cadu/avatars/${configured || AVATAR_BADGES[seed % AVATAR_BADGES.length]}`;
}

function writeCollectionPayload(event, item, kind, label) {
  if (!event.dataTransfer) return;
  const payload = {
    ...item,
    id: item.id,
    type: kind,
    kind,
    title: item.title || label,
    projectRef: item.projectRef || (kind === 'project' ? item.id : undefined),
    brandRef: item.brandRef || (kind === 'brand' ? `studio:${item.id}` : undefined),
  };
  const serialized = JSON.stringify(payload);
  event.dataTransfer.effectAllowed = 'copy';
  event.dataTransfer.setData('application/x-cadu-item', serialized);
  event.dataTransfer.setData('text/plain', serialized);
}

function SidebarBrandProjects({brands, projects, links}) {
  const {groups, ungrouped} = groupWorkspaceProjects(brands, projects);
  if (!groups.length && !ungrouped.length) return null;
  const projectLink = project => <a key={entityIdentity(project)} className="cadu-ds-context-sidebar__project-child" href={entityHref(project)} title={entityLabel(project, 'Projeto')}><Icon name="folder" size={14}/><span className="cadu-ds-context-sidebar__fade">{entityLabel(project, 'Projeto')}</span></a>;
  return <section className="cadu-ds-context-sidebar__brand-groups" aria-label="Marcas e projetos">
    <div className="cadu-ds-context-sidebar__section-label"><span>Projetos</span></div>
    {groups.slice(0, 4).map(brand => <section className="cadu-ds-context-sidebar__brand-group" key={entityIdentity(brand) || entityLabel(brand)}>
      <a className="cadu-ds-context-sidebar__brand-heading" href={entityHref(brand) || links.brands || '#'} title={entityLabel(brand, 'Marca')}><b className="cadu-ds-context-sidebar__fade">{entityLabel(brand, 'Marca')}</b></a>
      {brand.projects.length > 0 && <div className="cadu-ds-context-sidebar__project-tree">{brand.projects.slice(0, 3).map(projectLink)}</div>}
    </section>)}
    {ungrouped.length > 0 && <section className="cadu-ds-context-sidebar__brand-group">
      {groups.length > 0 && <span className="cadu-ds-context-sidebar__group-note">Sem marca</span>}
      <div className="cadu-ds-context-sidebar__project-tree cadu-ds-context-sidebar__project-tree--standalone">{ungrouped.slice(0, 3).map(projectLink)}</div>
    </section>}
  </section>;
}

export function WorkspaceContextSidebar({mode = 'home', preferenceKey = mode, bootstrap = {}, links = {}, active = '', agencyName: agencyNameProp = '', resources = [], projects: projectsProp = [], brands: brandsProp = [], rail = false, onCollapsedChange}) {
  // Every Workspace page receives the same unfiltered tree from the server.
  // Catalog pages filter their own lists, so those must never feed the rail.
  const shared = bootstrap.sidebar || {};
  const agencyName = shared.agency?.name || agencyNameProp;
  const brands = Array.isArray(shared.brands) ? shared.brands : brandsProp;
  const projects = Array.isArray(shared.projects) ? shared.projects : projectsProp;
  const [storedCollapsed, setCollapsed] = useState(() => readCollapsed(mode, preferenceKey));
  const collapsed = rail || storedCollapsed;
  const items = HOME_ITEMS;
  const recentFiles = useMemo(() => resources.filter(item => item?.href || item?.url).slice(0, 3), [resources]);
  const userName = String(bootstrap.user?.name || '').trim();
  const initialUsage = bootstrap.usagePercent ?? bootstrap.home?.usagePercent ?? bootstrap.account?.position?.usage_percentage;
  const usagePercent = useCreditUsage(initialUsage, bootstrap.endpoints?.creditSummary || undefined);
  const creditsHref = links.creditos || links.credits || links.uso || links.usage || '';

  useEffect(() => {
    let active = true;
    const refresh = () => fetch(bootstrap.endpoints?.creditSummary || '/workspace/api/creditos/resumo', {credentials: 'same-origin', headers: {Accept: 'application/json'}})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Resumo indisponível')))
      .then(value => { const percent = value.monthly_usage_percentage; if (active && percent !== undefined && percent !== null && percent !== '' && Number.isFinite(Number(percent))) setUsagePercent(Number(percent)); })
      .catch(() => {});
    refresh();
    const timer = window.setInterval(refresh, 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, [bootstrap.endpoints?.creditSummary]);

  useEffect(() => {
    if (rail) return;
    try { window.localStorage.setItem(`cadu:sidebar:${preferenceKey}`, collapsed ? 'collapsed' : 'open'); } catch (_) { /* local preference is optional */ }
  }, [collapsed, preferenceKey, rail]);
  useEffect(() => { onCollapsedChange?.(collapsed); }, [collapsed, onCollapsedChange]);

  return <aside className={`cadu-ds-context-sidebar is-${mode} ${collapsed ? 'is-collapsed' : ''}${rail ? ' is-rail' : ''}`} aria-label="Navegação do Workspace">
    <header className="cadu-ds-context-sidebar__header">
      {mode === 'home' ? <div className="cadu-ds-context-sidebar__solution"><CaduSolutionSwitcher logo={bootstrap.caduMark} solutions={workspaceSolutionItems(bootstrap)} activeId="workspace" showActiveLabel={!collapsed} overlay/></div> : null}
      {!rail && <button type="button" className="cadu-ds-context-sidebar__toggle" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? 'Abrir navegação' : 'Fechar navegação'} aria-expanded={!collapsed}><span className="cadu-ds-context-sidebar__toggle-mobile">{collapsed ? 'Menu' : 'Fechar'}</span><span className="cadu-ds-context-sidebar__toggle-desktop" aria-hidden="true">{collapsed ? '›' : '‹'}</span></button>}
    </header>
    {items.length > 0 && <nav className="cadu-ds-context-sidebar__nav" aria-label="Seções do Workspace">
      {items.map(item => { const href = links[item.key]; if (!href) return null; return <a key={item.id} href={href} className={active === item.id ? 'is-active' : ''} aria-current={active === item.id ? 'page' : undefined} title={collapsed ? item.label : undefined}><Icon name={item.icon} size={16}/><span>{item.label}</span></a>; })}
    </nav>}
    {mode === 'home' && <nav className="cadu-ds-context-sidebar__nav cadu-ds-context-sidebar__nav--mobile" aria-label="Destinos do Workspace">{MOBILE_HOME_ITEMS.map(item => links[item.key] ? <a key={item.id} href={links[item.key]}><Icon name={item.icon} size={16}/><span>{item.label}</span></a> : null)}</nav>}
    {mode === 'home' && <>
      <SidebarBrandProjects brands={brands} projects={projects} links={links}/>
    </>}
    {mode === 'home' && recentFiles.length > 0 && <section className="cadu-ds-context-sidebar__recent" aria-label="Arquivos recentes">
      <div className="cadu-ds-context-sidebar__section-label"><span>Arquivos recentes</span>{links.docs && <a href={links.docs} title="Abrir todos os arquivos">Ver todos</a>}</div>
      {recentFiles.map(item => <a key={item.id || item.resourceRef} href={item.href || item.url} title={item.title || item.name}><Icon name="file" size={14}/><span><b>{item.title || item.name || 'Arquivo'}</b><small>{item.projectName || item.project_name || 'Workspace'}</small></span></a>)}
    </section>}
    {mode === 'home' && !brands.length && <p className="cadu-ds-context-sidebar__empty">Nenhuma marca disponível.</p>}
    <footer className="cadu-ds-context-sidebar__footer">
      <SidebarAccount userName={userName} agencyName={agencyName} avatar={workspaceUserPhoto(bootstrap.user)} fallbackAvatar={bootstrap.user?.photoFallback || avatarBadgeSource(bootstrap.user)} profileUrl={links.perfil || links.profile || links.agencia || links.home || '/workspace/app'} creditsUrl={creditsHref} usagePercent={usagePercent} active={active === 'conta'}/>
    </footer>
  </aside>;
}
