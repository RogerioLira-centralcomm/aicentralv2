import React, {useEffect, useMemo, useState} from 'react';
import {Icon} from './Icon';
import {VisualIdentity} from './VisualIdentity';

const HOME_ITEMS = [
  {id: 'home', label: 'Início', key: 'home', icon: 'home'},
];

const ACCOUNT_ITEMS = [
  {id: 'agencia', label: 'Agência', key: 'agencia', icon: 'home'},
  {id: 'equipe', label: 'Equipe', key: 'equipe', icon: 'folder'},
  {id: 'faturamento', label: 'Faturamento', key: 'faturamento', icon: 'file'},
  {id: 'integracoes', label: 'Integrações', key: 'integracoes', icon: 'external'},
  {id: 'planos', label: 'Plano', key: 'planos', icon: 'pulse'},
  {id: 'perfil', label: 'Perfil', key: 'perfil', icon: 'brand'},
  {id: 'creditos', label: 'Uso e créditos', key: 'creditos', icon: 'history'},
];

function readCollapsed(mode) {
  try { return window.localStorage.getItem(`cadu:sidebar:${mode}`) === 'collapsed'; } catch (_) { return false; }
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
    {items.slice(0, 5).map((item, index) => {
      const labelText = item.name || item.title || (kind === 'brand' ? 'Marca' : 'Projeto');
      return <a key={item.id || item.ref || item.href} className="cadu-ds-context-sidebar__collection-item" href={item.href || item.url || '#'} title={labelText} draggable onDragStart={event => writeCollectionPayload(event, item, kind, labelText)}>
        <span className="cadu-ds-context-sidebar__collection-identity">
          <VisualIdentity src={kind === 'brand' ? item.logoUrl : item.previewUrl || item.dockLogoUrl} initials={item.visualInitials || labelText} label={labelText} color={item.visualColor} variant={item.visualVariant}/>
          {kind === 'project' && <small className="cadu-ds-context-sidebar__collection-index" aria-hidden="true">{index + 1}</small>}
        </span>
        <span><b>{labelText}</b>{kind === 'brand' && item.projectCount > 0 && <small>{item.projectCount} {item.projectCount === 1 ? 'projeto' : 'projetos'}</small>}</span>
      </a>;
    })}
  </section>;
}

export function WorkspaceContextSidebar({mode = 'home', links = {}, active = 'home', resources = [], projects = [], brands = [], conversations = [], agencyName = ''}) {
  // Account navigation is a persistent context on every account page. It
  // starts open even if the workspace/home rail was previously collapsed.
  const [collapsed, setCollapsed] = useState(() => mode === 'account' ? false : readCollapsed(mode));
  const items = mode === 'account' ? ACCOUNT_ITEMS : HOME_ITEMS;
  const recentFiles = useMemo(() => resources.filter(item => item?.href || item?.url).slice(0, 3), [resources]);
  const recentConversations = useMemo(() => conversations.filter(item => item?.href || item?.url).slice(0, 5), [conversations]);

  useEffect(() => {
    try { window.localStorage.setItem(`cadu:sidebar:${mode}`, mode === 'account' ? 'open' : collapsed ? 'collapsed' : 'open'); } catch (_) { /* local preference is optional */ }
  }, [collapsed, mode]);

  return <aside className={`cadu-ds-context-sidebar ${collapsed ? 'is-collapsed' : ''}`} aria-label={mode === 'account' ? 'Navegação da conta' : 'Navegação do Workspace'}>
    <header className="cadu-ds-context-sidebar__header">
      <div className="cadu-ds-context-sidebar__heading"><span>{mode === 'account' ? 'Conta' : 'Workspace'}</span><strong>{agencyName || 'Minha agência'}</strong></div>
      <button type="button" className="cadu-ds-context-sidebar__toggle" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? 'Expandir navegação' : 'Recolher navegação'} aria-expanded={!collapsed}>{collapsed ? '›' : '‹'}</button>
    </header>
    <nav className="cadu-ds-context-sidebar__nav" aria-label={mode === 'account' ? 'Seções da conta' : 'Seções do Workspace'}>
      {items.map(item => { const href = links[item.key]; if (!href) return null; return <a key={item.id} href={href} className={active === item.id ? 'is-active' : ''} aria-current={active === item.id ? 'page' : undefined} title={collapsed ? item.label : undefined}><Icon name={item.icon} size={16}/><span>{item.label}</span></a>; })}
    </nav>
    {mode === 'home' && <>
      <SidebarCollection label="Projetos" href={links.projects} items={projects} kind="project" />
      <SidebarCollection label="Marcas" href={links.brands} items={brands} kind="brand" />
    </>}
    {mode === 'home' && recentFiles.length > 0 && <section className="cadu-ds-context-sidebar__recent" aria-label="Arquivos recentes">
      <div className="cadu-ds-context-sidebar__section-label"><span>Arquivos recentes</span>{links.docs && <a href={links.docs} title="Abrir todos os arquivos">Ver todos</a>}</div>
      {recentFiles.map(item => <a key={item.id || item.resourceRef} href={item.href || item.url} title={item.title || item.name}><Icon name="file" size={14}/><span><b>{item.title || item.name || 'Arquivo'}</b><small>{item.projectName || item.project_name || 'Workspace'}</small></span></a>)}
    </section>}
    {mode === 'home' && recentFiles.length === 0 && recentConversations.length >= 5 && <section className="cadu-ds-context-sidebar__recent" aria-label="Conversas recentes">
      <div className="cadu-ds-context-sidebar__section-label"><span>Conversas recentes</span>{links.conversations && <a href={links.conversations}>Ver todas</a>}</div>
      {recentConversations.map(item => <a key={item.id || item.conversationId || item.href} href={item.href || item.url} title={item.title || item.name}><Icon name="history" size={14}/><span><b>{item.title || item.name || 'Conversa'}</b><small>{item.context || item.projectName || 'Cadu Chat'}</small></span></a>)}
    </section>}
  </aside>;
}
