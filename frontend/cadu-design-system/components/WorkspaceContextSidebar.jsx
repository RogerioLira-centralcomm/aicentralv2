import React, {useEffect, useMemo, useState} from 'react';
import {Icon} from './Icon';
import {VisualIdentity} from './VisualIdentity';

// The home surface is already the current destination. Keep its context rail
// focused on work shortcuts instead of repeating an "Início" navigation item.
const HOME_ITEMS = [];

const ACCOUNT_ITEMS = [
  {id: 'agencia', label: 'Agência', key: 'agencia', icon: 'home'},
  {id: 'equipe', label: 'Equipe', key: 'equipe', icon: 'folder'},
  {id: 'faturamento', label: 'Faturamento', key: 'faturamento', icon: 'file'},
  {id: 'integracoes', label: 'Integrações', key: 'integracoes', icon: 'external'},
  {id: 'planos', label: 'Plano', key: 'planos', icon: 'pulse'},
  {id: 'perfil', label: 'Perfil', key: 'perfil', icon: 'brand'},
  {id: 'uso', label: 'Uso', key: 'uso', icon: 'pulse'},
  {id: 'creditos', label: 'Créditos', key: 'creditos', icon: 'history'},
];

function readCollapsed(mode) {
  try { return window.localStorage.getItem(`cadu:sidebar:${mode}`) === 'collapsed'; } catch (_) { return false; }
}

function conversationHref(item, baseHref) {
  const directHref = item?.href || item?.url;
  const rawId = item?.conversationId || item?.id;
  const conversationId = String(rawId || '').startsWith('conversation:') ? String(rawId).slice('conversation:'.length) : rawId;
  if (!baseHref || !conversationId) return directHref || '';
  try {
    const target = new URL(baseHref, window.location.origin);
    target.searchParams.set('conversation_id', conversationId);
    target.searchParams.set('history', '1');
    if (item?.projectRef) target.searchParams.set('project_ref', item.projectRef);
    return `${target.pathname}${target.search}`;
  } catch (_) {
    return directHref || '';
  }
}

function projectConversationHref(project, baseHref) {
  if (!baseHref) return project?.href || project?.url || '#';
  try {
    const target = new URL(baseHref, window.location.origin);
    target.searchParams.set('project_ref', project.projectRef || project.ref || project.id);
    return `${target.pathname}${target.search}`;
  } catch (_) {
    return project?.href || project?.url || '#';
  }
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

function SidebarCollection({label, href, items, kind}) {
  if (!items.length) return null;
  return <section className="cadu-ds-context-sidebar__collection" aria-label={label}>
    <div className="cadu-ds-context-sidebar__section-label"><span>{label}</span>{href && <a href={href}>Ver todos</a>}</div>
    {items.slice(0, 5).map(item => {
      const labelText = item.name || item.title || (kind === 'brand' ? 'Marca' : 'Projeto');
      return <a key={item.id || item.ref || item.href} className="cadu-ds-context-sidebar__collection-item" href={item.href || item.url || '#'} title={labelText} draggable onDragStart={event => writeCollectionPayload(event, item, kind, labelText)}>
        <span className="cadu-ds-context-sidebar__collection-identity">
          <VisualIdentity src={kind === 'brand' ? item.logoUrl : item.previewUrl || item.dockLogoUrl} initials={item.visualInitials || labelText} label={labelText} color={item.visualColor} variant={item.visualVariant} imageTreatment={kind === 'brand' ? 'brand' : ''}/>
        </span>
        <span><b>{labelText}</b>{kind === 'brand' && item.projectCount > 0 && <small>{item.projectCount} {item.projectCount === 1 ? 'projeto' : 'projetos'}</small>}</span>
      </a>;
    })}
  </section>;
}

function SidebarBrandProjectGroups({brands, projects, links}) {
  const brandRef = item => String(item?.ref || item?.brandRef || `studio:${item?.id || ''}`);
  const groups = brands.map(brand => {
    const ref = brandRef(brand);
    return {...brand, projects: projects.filter(project => {
      const refs = project.related_refs || project.relatedRefs || (project.brandRef ? [project.brandRef] : []);
      return refs.map(String).includes(ref) || String(project.brandRef || '') === ref;
    }).slice(0, 5)};
  });
  const groupedProjects = new Set(groups.flatMap(group => group.projects.map(project => String(project.id || project.ref || project.projectRef))));
  const ungrouped = projects.filter(project => !groupedProjects.has(String(project.id || project.ref || project.projectRef))).slice(0, 5);
  if (!groups.length && !ungrouped.length) return null;
  return <section className="cadu-ds-context-sidebar__brand-groups" aria-label="Marcas e projetos">
    <div className="cadu-ds-context-sidebar__section-label"><span>Marcas e projetos</span>{links.projects && <a href={links.projects}>Ver todos</a>}</div>
    {groups.map(brand => <section className="cadu-ds-context-sidebar__brand-group" key={brand.id || brand.ref}>
      <a className="cadu-ds-context-sidebar__brand-heading" href={brand.href || '#'} title={brand.name || brand.title}>
        <VisualIdentity src={brand.logoUrl} initials={brand.visualInitials || brand.name} label={brand.name} color={brand.visualColor} variant={brand.visualVariant} imageTreatment="brand"/><b>{brand.name}</b>
      </a>
      {brand.projects.map(project => <a key={project.id || project.ref || project.projectRef} className="cadu-ds-context-sidebar__project-child" href={projectConversationHref(project, links.conversations)} title={project.name || project.title} draggable onDragStart={event => writeCollectionPayload(event, project, 'project', project.name || project.title || 'Projeto')}><VisualIdentity src={project.previewUrl || project.logoUrl || project.dockLogoUrl} initials={project.visualInitials || project.name} label={project.name || project.title} color={project.visualColor || '#176b5e'} variant={project.visualVariant}/><span>{project.name || project.title || 'Projeto'}</span></a>)}
    </section>)}
    {ungrouped.length > 0 && <section className="cadu-ds-context-sidebar__brand-group cadu-ds-context-sidebar__brand-group--ungrouped"><span className="cadu-ds-context-sidebar__brand-heading-label">Outros projetos</span>{ungrouped.map(project => <a key={project.id || project.ref || project.projectRef} className="cadu-ds-context-sidebar__project-child" href={projectConversationHref(project, links.conversations)} title={project.name || project.title} draggable onDragStart={event => writeCollectionPayload(event, project, 'project', project.name || project.title || 'Projeto')}><VisualIdentity src={project.previewUrl || project.logoUrl || project.dockLogoUrl} initials={project.visualInitials || project.name} label={project.name || project.title} color={project.visualColor || '#176b5e'} variant={project.visualVariant}/><span>{project.name || project.title || 'Projeto'}</span></a>)}</section>}
  </section>;
}

export function WorkspaceContextSidebar({mode = 'home', links = {}, active = 'home', resources = [], projects = [], brands = [], conversations = [], agencyName = ''}) {
  // Account navigation is a persistent context on every account page. It
  // starts open even if the workspace/home rail was previously collapsed.
  const [collapsed, setCollapsed] = useState(() => mode === 'account' ? false : readCollapsed(mode));
  const items = mode === 'account' ? ACCOUNT_ITEMS : HOME_ITEMS;
  const recentFiles = useMemo(() => resources.filter(item => item?.href || item?.url).slice(0, 3), [resources]);
  const recentConversations = useMemo(() => conversations.map(item => ({...item, href: conversationHref(item, links.conversations)})).filter(item => item.href), [conversations, links.conversations]);
  const visibleRecentConversations = recentConversations.length >= 5 ? recentConversations.slice(0, 5) : recentConversations;

  useEffect(() => {
    try { window.localStorage.setItem(`cadu:sidebar:${mode}`, mode === 'account' ? 'open' : collapsed ? 'collapsed' : 'open'); } catch (_) { /* local preference is optional */ }
  }, [collapsed, mode]);

  return <aside className={`cadu-ds-context-sidebar ${collapsed ? 'is-collapsed' : ''}`} aria-label={mode === 'account' ? 'Navegação da conta' : 'Navegação do Workspace'}>
    <header className="cadu-ds-context-sidebar__header">
      <div className="cadu-ds-context-sidebar__heading"><span>{mode === 'account' ? 'Conta' : 'Workspace'}</span><strong>{agencyName || 'Cliente'}</strong></div>
      <button type="button" className="cadu-ds-context-sidebar__toggle" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? 'Expandir navegação' : 'Recolher navegação'} aria-expanded={!collapsed}>{collapsed ? '›' : '‹'}</button>
    </header>
    {items.length > 0 && <nav className="cadu-ds-context-sidebar__nav" aria-label={mode === 'account' ? 'Seções da conta' : 'Seções do Workspace'}>
      {items.map(item => { const href = links[item.key]; if (!href) return null; return <a key={item.id} href={href} className={active === item.id ? 'is-active' : ''} aria-current={active === item.id ? 'page' : undefined} title={collapsed ? item.label : undefined}><Icon name={item.icon} size={16}/><span>{item.label}</span></a>; })}
    </nav>}
    {mode === 'home' && <>
      <SidebarBrandProjectGroups brands={brands} projects={projects} links={links}/>
    </>}
    {mode === 'home' && recentFiles.length > 0 && <section className="cadu-ds-context-sidebar__recent" aria-label="Arquivos recentes">
      <div className="cadu-ds-context-sidebar__section-label"><span>Arquivos recentes</span>{links.docs && <a href={links.docs} title="Abrir todos os arquivos">Ver todos</a>}</div>
      {recentFiles.map(item => <a key={item.id || item.resourceRef} href={item.href || item.url} title={item.title || item.name}><Icon name="file" size={14}/><span><b>{item.title || item.name || 'Arquivo'}</b><small>{item.projectName || item.project_name || 'Workspace'}</small></span></a>)}
    </section>}
    {mode === 'home' && recentConversations.length > 0 && <section className="cadu-ds-context-sidebar__recent" aria-label="Conversas recentes">
      <div className="cadu-ds-context-sidebar__section-label"><span>Conversas recentes</span>{links.conversations && <a href={links.conversations}>Ver todas</a>}</div>
      {visibleRecentConversations.map(item => <a key={item.id || item.conversationId || item.href} href={item.href || item.url} title={item.title || item.name}><span><b>{item.title || item.name || 'Conversa'}</b></span></a>)}
    </section>}
    {mode === 'home' && !brands.length && <p className="cadu-ds-context-sidebar__empty">Nenhuma marca disponível.</p>}
    {mode === 'home' && !recentConversations.length && <p className="cadu-ds-context-sidebar__empty">As conversas recentes aparecerão aqui.</p>}
  </aside>;
}
