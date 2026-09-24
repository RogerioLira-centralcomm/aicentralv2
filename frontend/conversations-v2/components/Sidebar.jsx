import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {request} from '../lib/api';
import {conversationDisplayTitle} from '../lib/conversationPresentation.mjs';
import {workspaceMobileDestinationItems, workspaceMobileSolutionItems} from '../../cadu-design-system/workspaceSolutions';
import {CaduSolutionSwitcher} from '../../cadu-design-system/components/WorkspaceSelectors';
import {VisualIdentity} from '../../cadu-design-system/components/VisualIdentity';
import {DockUsageRing} from '../../cadu-design-system/components/CaduDock';
import {Icon} from '../../cadu-design-system/components/Icon';
import {useWorkspaceNotifications} from '../../cadu-design-system/components/WorkspaceNotifications';
import {brandIdentityKeys, isArchivedEntity, projectBrandKeys} from '../../cadu-design-system/workspaceEntities.mjs';

function contextLabel(item, projects, brands) {
  const project = projects.find(candidate => (candidate.ref || candidate.projectRef || candidate.id) === item.project_ref);
  if (project) return project.name;
  const brand = brands.find(candidate => (candidate.ref || candidate.brandRef || `studio:${candidate.id}`) === item.brand_ref);
  return brand ? brand.name : '';
}

function NavIcon({name}) {
  return <span className={`cv-nav-icon is-${name}`} aria-hidden="true"/>;
}

function UsageMiniChart({percent}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  const formatted = new Intl.NumberFormat('pt-BR', {maximumFractionDigits:1}).format(value);
  return <span className="cv-usage-mini" role="img" aria-label={`Utilização de créditos: ${formatted}%`} title="Créditos e consumo">
    <span>{formatted}%</span><i aria-hidden="true"><b style={{width:`${value}%`}}/></i>
  </span>;
}

function SidebarTitle({children, className = ''}) {
  const viewport = useRef(null);
  const content = useRef(null);
  const [overflow, setOverflow] = useState(0);
  useEffect(() => {
    const measure = () => {
      const node = viewport.current;
      const styles = node ? window.getComputedStyle(node) : null;
      const horizontalPadding = styles ? Number.parseFloat(styles.paddingLeft) + Number.parseFloat(styles.paddingRight) : 0;
      const availableWidth = Math.max(0, (node?.clientWidth || 0) - horizontalPadding);
      const difference = Math.max(0, (content.current?.scrollWidth || 0) - availableWidth);
      setOverflow(current => current === difference ? current : difference);
    };
    measure();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    if (viewport.current) observer?.observe(viewport.current);
    if (content.current) observer?.observe(content.current);
    window.addEventListener('resize', measure);
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure); };
  }, [children]);
  const style = overflow ? {'--cv-title-scroll': `-${overflow}px`, '--cv-title-duration': `${Math.min(10, Math.max(4, Math.ceil(overflow / 48)))}s`} : undefined;
  return <span ref={viewport} className={`cv-sidebar-title${overflow ? ' is-overflowing' : ''}${className ? ` ${className}` : ''}`} style={style}><span ref={content} className="cv-sidebar-title__text">{children}</span></span>;
}

export function Sidebar({conversations, projects = [], brands = [], activeProjectRef = '', activeBrandRef = '', artifactOpen = false, pluginsPageOpen = false, navUrls = {}, solutions = [], logo, user = {}, usagePercent = 0, activeId, currentTitle = '', onOpen, onOpenLibrary, onOpenResource, onOpenLibraryRef, onOpenBrandArtifact, onOpenPlugins, onClosePlugins, onNewConversation, onProjectChange, onConversationAction, open, onOpenSidebar, onClose, loading, openingId}) {
  const sidebarRef = useRef(null);
  const previousFocus = useRef(null);
  const [showAllRecent, setShowAllRecent] = useState(false);
  const [showAllBrands, setShowAllBrands] = useState(false);
  const [showMoreProjects, setShowMoreProjects] = useState(false);
  const [showMoreBrandProjects, setShowMoreBrandProjects] = useState({});
  const [showAllProjectConversations, setShowAllProjectConversations] = useState({});
  const [expandedProjects, setExpandedProjects] = useState(() => new Set(activeProjectRef ? [String(activeProjectRef)] : []));
  const [expandedBrands, setExpandedBrands] = useState(() => new Set(activeBrandRef ? [String(activeBrandRef)] : []));
  const [projectMenuId, setProjectMenuId] = useState('');
  const [actionMenuId, setActionMenuId] = useState('');
  const notifications = useWorkspaceNotifications();
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [spotlightQuery, setSpotlightQuery] = useState('');
  const [spotlightResults, setSpotlightResults] = useState([]);
  const [spotlightLoading, setSpotlightLoading] = useState(false);
  const [spotlightError, setSpotlightError] = useState('');
  const spotlightInput = useRef(null);
  const searchSequence = useRef(0);
  const desktopMode = window.matchMedia('(min-width: 768px)').matches;
  const desktopClosed = desktopMode && !open;
  const ordered = conversations;
  const filtered = ordered;
  const activeProject = projects.find(item => String(item.ref || item.projectRef || item.id) === String(activeProjectRef));
  const activeBrand = brands.find(item => String(item.ref || item.brandRef || (item.id ? `studio:${item.id}` : '')) === String(activeBrandRef));
  const projectId = String(activeProject?.id || activeProjectRef || '').replace(/^ci:/, '');
  const projectDetailsUrl = projectId ? `/projetos/${encodeURIComponent(projectId)}` : '';
  const projectActivityUrl = projectId ? `/projetos/${encodeURIComponent(projectId)}/activity` : '';
  const projectTasksUrl = projectId ? `/projetos/${encodeURIComponent(projectId)}/tasks` : '';

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = event => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !window.matchMedia('(max-width: 767px)').matches) return undefined;
    previousFocus.current = document.activeElement;
    window.requestAnimationFrame(() => sidebarRef.current?.querySelector('.cv-mobile-navigation>header button')?.focus());
    const trapFocus = event => {
      if (event.key !== 'Tab') return;
      const controls = Array.from(sidebarRef.current?.querySelectorAll('.cv-mobile-navigation button:not(:disabled), .cv-mobile-navigation input, .cv-mobile-navigation a[href]') || []).filter(item => item.getClientRects().length);
      if (!controls.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', trapFocus);
    return () => { document.removeEventListener('keydown', trapFocus); window.requestAnimationFrame(() => previousFocus.current?.focus?.()); };
  }, [open]);

  useEffect(() => {
    if (!actionMenuId) return undefined;
    const close = event => {
      if (!event.target.closest('.cv-conversation-actions')) setActionMenuId('');
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [actionMenuId]);

  useEffect(() => {
    if (!projectMenuId) return undefined;
    const close = event => {
      if (!event.target.closest('.cv-project-menu')) setProjectMenuId('');
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [projectMenuId]);

  useEffect(() => {
    if (!spotlightOpen) return undefined;
    window.requestAnimationFrame(() => spotlightInput.current?.focus());
    const close = event => { if (event.key === 'Escape') setSpotlightOpen(false); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [spotlightOpen]);

  useEffect(() => {
    const query = spotlightQuery.trim();
    const sequence = ++searchSequence.current;
    if (!spotlightOpen || query.length < 2) {
      setSpotlightResults([]); setSpotlightLoading(false); setSpotlightError('');
      return undefined;
    }
    const timer = window.setTimeout(async () => {
      setSpotlightLoading(true); setSpotlightError('');
      try {
        if (!projectId) {
          const localResults = conversations.filter(item => `${item.title || ''} ${contextLabel(item, projects, brands)}`.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR'))).slice(0, 20).map(item => ({id: item.id, kind: 'conversation', title: item.title || 'Conversa', detail: contextLabel(item, projects, brands)}));
          if (sequence === searchSequence.current) setSpotlightResults(localResults);
          return;
        }
        const data = await request(`/workspace/api/projetos/${encodeURIComponent(projectId)}/buscar?q=${encodeURIComponent(query)}`);
        const conversationResults = conversations.filter(item => String(item.project_ref || '') === String(activeProjectRef) && `${item.title || ''}`.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR'))).slice(0, 10).map(item => ({id: item.id, kind: 'conversation', title: item.title || 'Conversa'}));
        if (sequence === searchSequence.current) setSpotlightResults([...(data.results || []), ...conversationResults].slice(0, 40));
      } catch (error) {
        if (sequence === searchSequence.current) { setSpotlightResults([]); setSpotlightError(error.message || 'Não foi possível pesquisar o projeto.'); }
      } finally { if (sequence === searchSequence.current) setSpotlightLoading(false); }
    }, 160);
    return () => window.clearTimeout(timer);
  }, [spotlightOpen, spotlightQuery, projectId, conversations, projects, brands, activeProjectRef]);

  useEffect(() => {
    if (!activeProjectRef) return;
    const ref = String(activeProjectRef);
    setExpandedProjects(current => current.has(ref) ? current : new Set([...current, ref]));
  }, [activeProjectRef]);

  useEffect(() => {
    if (!activeBrandRef) return;
    const ref = String(activeBrandRef);
    setExpandedBrands(current => current.has(ref) ? current : new Set([...current, ref]));
  }, [activeBrandRef]);

  useEffect(() => {
    const sortedBrands = brands.filter(item => !isArchivedEntity(item)).sort((left, right) => String(left.name || left.title || '').localeCompare(String(right.name || right.title || ''), 'pt-BR', {sensitivity: 'base'}));
    const activeIndex = sortedBrands.findIndex(item => String(item.ref || item.brandRef || (item.id ? `studio:${item.id}` : item.name)) === String(activeBrandRef));
    if (activeIndex >= 5) setShowAllBrands(true);
  }, [activeBrandRef, brands]);

  if (!open && !desktopMode) return null;
  const brandConversations = filtered.filter(item => String(item.brand_ref || '') === String(activeBrandRef) && item.section !== 'automation');
  const automations = filtered.filter(item => item.section === 'automation' && item.automation_enabled);
  const standard = filtered.filter(item => !item.project_ref && !item.brand_ref && item.section !== 'automation');
  const activeConversation = conversations.find(item => String(item.id) === String(activeId));
  const mobileDestinations = workspaceMobileDestinationItems(navUrls);
  const mobileSolutions = workspaceMobileSolutionItems(navUrls);
  const projectItems = [...projects].sort((left, right) => String(left.name || left.title || '').localeCompare(String(right.name || right.title || ''), 'pt-BR', {sensitivity: 'base'}));
  const brandItems = brands.filter(item => !isArchivedEntity(item)).sort((left, right) => String(left.name || left.title || '').localeCompare(String(right.name || right.title || ''), 'pt-BR', {sensitivity: 'base'}));
  const projectsForBrand = brand => {
    const keys = brandIdentityKeys(brand);
    return projectItems.filter(project => projectBrandKeys(project).some(key => keys.has(key)));
  };
  const toggleProject = ref => {
    const key = String(ref);
    setExpandedProjects(current => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  };
  const toggleBrand = (ref, brand) => {
    const key = String(ref);
    setExpandedBrands(current => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
    if (!artifactOpen) onOpenBrandArtifact?.(brand.id ? `studio:${brand.id}` : brand.brandRef || brand.ref || key);
  };
  const openIndex = ref => { if (ref || activeProjectRef) onOpenLibrary?.(true, ref || activeProjectRef); else setSpotlightError('Selecione um projeto para abrir os arquivos.'); };
  const startProjectConversation = async ref => {
    if (String(ref) !== String(activeProjectRef)) await onProjectChange?.(ref);
    onNewConversation?.();
  };
  const runAction = (event, item, action) => {
    event.stopPropagation();
    setActionMenuId('');
    onConversationAction?.(item, action);
  };
  const conversationList = (items, hideContext = false) => items.map(item => { const context = contextLabel(item, projects, brands); return <div className="cv-conversation-row" key={item.id}>
    <button className="cv-conversation-card" type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={conversationDisplayTitle(item.title, 'Chat sem título')}><span className="cv-conversation-card__copy"><b><SidebarTitle>{conversationDisplayTitle(item.title, 'Chat sem título')}</SidebarTitle></b>{!hideContext && <small>{context || 'Sessão livre'}</small>}</span></button>
    <div className={`cv-conversation-actions ${String(actionMenuId) === String(item.id) ? 'is-open' : ''}`}>
      <button type="button" className="cv-conversation-actions__trigger" aria-label={`Ações de ${item.title || 'conversa'}`} aria-expanded={String(actionMenuId) === String(item.id)} onClick={event => { event.stopPropagation(); setActionMenuId(current => String(current) === String(item.id) ? '' : String(item.id)); }}><span aria-hidden="true">…</span></button>
      {String(actionMenuId) === String(item.id) && <div className="cv-conversation-actions__menu" role="menu">
        {item.section === 'automation' && item.automation_enabled && <button type="button" onClick={event => runAction(event, item, 'stop-automation')}>Encerrar automação</button>}
        <button type="button" className="is-danger" onClick={event => runAction(event, item, 'archive')}>Arquivar</button>
      </div>}
    </div>
  </div>; });
  return <>
    {open && <button type="button" onClick={onClose} aria-label="Fechar chats recentes" className="cv-recent-backdrop is-visible"/>}
    <aside ref={sidebarRef} id="cv-recent-sidebar" role={!desktopMode ? 'dialog' : undefined} aria-modal={!desktopMode ? 'true' : undefined} className={`cv-recent-sidebar ${desktopClosed ? 'is-closed' : 'is-open'}`} aria-label="Chats recentes">
      {desktopClosed ? <div className="cv-sidebar-mini-rail">
        <div className="cv-sidebar-mini-rail__top"><CaduSolutionSwitcher logo={logo} solutions={solutions} activeId="workspace"/><button type="button" className="cv-sidebar-icon-button" onClick={onOpenSidebar} aria-label="Expandir sidebar" title="Expandir sidebar"><NavIcon name="expand"/></button></div>
      </div> : <>
      <div className="cv-mobile-navigation">
        <header><div><strong>Workspace</strong><small>{conversationDisplayTitle(currentTitle || activeConversation?.title, 'Novo chat')}</small></div><button type="button" onClick={onClose} aria-label="Fechar navegação"><NavIcon name="close"/></button></header>
        <div className="cv-mobile-navigation__scroll">
          <button type="button" className="cv-mobile-navigation__primary" onClick={onNewConversation}>Novo chat</button>
          {activeProject && projectDetailsUrl && <a className="cv-mobile-navigation__project-link" href={projectDetailsUrl} onClick={onClose}><NavIcon name="folder"/><span>{activeProject.name || activeProject.title}</span></a>}
          <div className="cv-sidebar-project-tools"><button type="button" title="Buscar no projeto" aria-label="Buscar no projeto" onClick={() => { setSpotlightQuery(''); setSpotlightOpen(true); }}><NavIcon name="search"/></button></div>
          {!!automations.length && <section><h2>Automações</h2>{conversationList(automations.slice(0, 5))}</section>}
          <section><h2>Chats recentes</h2>{conversationList(standard.slice(0, 5))}{standard.length > 5 && <button type="button" className="cv-mobile-navigation__more" onClick={event => { event.currentTarget.closest('section')?.classList.add('is-expanded'); }}>Ver todos</button>}{standard.length > 5 && <div className="cv-mobile-navigation__extra">{conversationList(standard.slice(5))}</div>}</section>
          {!!mobileDestinations.length && <nav className="cv-mobile-navigation__destinations" aria-label="Áreas do Workspace"><h2>Workspace</h2>{mobileDestinations.map(item => <a key={item.id} href={item.href} onClick={onClose}><NavIcon name={item.icon}/><span>{item.name}</span></a>)}</nav>}
          {!!mobileSolutions.length && <nav className="cv-mobile-navigation__solutions" aria-label="Outras soluções"><h2>Outras soluções</h2>{mobileSolutions.map(item => <a key={item.id} href={item.href} onClick={onClose}><span><b>{item.name}</b><small>{item.description}</small></span></a>)}</nav>}
          {navUrls.profile && <nav className="cv-mobile-navigation__account" aria-label="Conta"><a href={navUrls.profile} onClick={onClose}><NavIcon name="brand"/><span>Conta e configurações</span></a></nav>}
        </div>
      </div>
      <div className="cv-desktop-history">
      <header className="cv-recent-sidebar__header">
        <div className="cv-chat-solution-switcher"><CaduSolutionSwitcher logo={logo} solutions={solutions} activeId="workspace"/></div>
        <div className="cv-recent-sidebar__tools"><button type="button" className="cv-sidebar-icon-button" onClick={() => { setSpotlightQuery(''); setSpotlightOpen(true); }} aria-label="Buscar conversas" title="Buscar conversas"><NavIcon name="search"/></button>{notifications.open && <button type="button" className="cv-sidebar-icon-button cv-sidebar-notifications" onClick={notifications.open} aria-label={notifications.pending.length ? `Abrir notificações, ${notifications.pending.length} pendentes` : 'Abrir notificações'} title="Notificações"><Icon name="pulse" size={17}/>{notifications.pending.length > 0 && <i>{notifications.pending.length > 9 ? '9+' : notifications.pending.length}</i>}</button>}<button type="button" className="cv-sidebar-icon-button" onClick={onClose} aria-label="Fechar navegação" title="Fechar navegação"><NavIcon name="collapse"/></button></div>
      </header>
      <div className="cv-recent-list">
        <nav className="cv-sidebar-primary-nav" aria-label="Navegação principal">
          {navUrls.home && <a className="cv-nav-action" href={navUrls.home}><Icon name="home" size={17}/><span>Início</span></a>}
          <button className="cv-nav-action" type="button" onClick={onNewConversation}><Icon name="newChat" size={17}/><span>Novo chat</span></button>
          <div className="cv-sidebar-primary-nav__scheduled"><button className="cv-nav-action" type="button" aria-expanded={automations.length > 0 ? showAllRecent : undefined} onClick={() => automations.length ? setShowAllRecent(value => !value) : null}><NavIcon name="clock"/><span>Agendado</span>{automations.length > 0 && <b>{automations.length}</b>}</button>{automations.length > 0 && showAllRecent && <div className="cv-sidebar-primary-nav__scheduled-items">{conversationList(automations)}</div>}</div>
          <button className={`cv-nav-action${pluginsPageOpen ? ' is-active' : ''}`} type="button" aria-current={pluginsPageOpen ? 'page' : undefined} onClick={pluginsPageOpen ? onClosePlugins : onOpenPlugins}><NavIcon name="plugin"/><span>Plugins</span></button>
          <button className="cv-nav-action" type="button" onClick={() => openIndex(activeProjectRef)}><NavIcon name="library"/><span>Arquivos</span></button>
        </nav>
        {!!brandItems.length && <section className="cv-nav-group cv-project-tree cv-brand-tree" aria-label="Marcas"><header><span>Marcas</span><b>{brandItems.length}</b></header>{brandItems.slice(0, showAllBrands ? undefined : 5).map(brand => {
          const ref = String(brand.ref || brand.brandRef || (brand.id ? `studio:${brand.id}` : brand.name));
          const isOpen = expandedBrands.has(ref);
          const relatedProjects = projectsForBrand(brand);
          return <section key={ref} className={`cv-project-tree__item cv-brand-tree__item${isOpen ? ' is-open' : ''}${String(activeBrandRef) === ref ? ' is-active' : ''}`}>
            <button type="button" className="cv-project-tree__trigger cv-brand-tree__trigger" aria-expanded={isOpen} aria-current={String(activeBrandRef) === ref ? 'location' : undefined} onClick={() => toggleBrand(ref, brand)}><SidebarTitle className="cv-project-tree__name">{brand.name || brand.title || 'Marca'}</SidebarTitle></button>
            {isOpen && <div className="cv-project-tree__children cv-brand-tree__children">{relatedProjects.slice(0, showMoreBrandProjects[ref] ? 10 : 6).map(project => {
              const projectRef = String(project.ref || project.projectRef || project.id);
              const projectIsOpen = expandedProjects.has(projectRef);
              const items = filtered.filter(item => String(item.project_ref || '') === projectRef && item.section !== 'automation');
              const showAllConversations = Boolean(showAllProjectConversations[projectRef]);
              const projectName = project.name || project.title || 'Projeto';
              const selected = projectRef === String(activeProjectRef);
              return <section key={projectRef} className={`cv-project-tree__item cv-brand-tree__project${projectIsOpen ? ' is-open' : ''}${selected ? ' is-active' : ''}`}>
                <button type="button" className="cv-project-tree__trigger" aria-expanded={projectIsOpen} aria-current={selected ? 'location' : undefined} onClick={() => { toggleProject(projectRef); if (!selected) onProjectChange?.(projectRef); }}><NavIcon name={projectIsOpen ? 'folderOpen' : 'folder'}/><SidebarTitle className="cv-project-tree__name">{projectName}</SidebarTitle></button>
                {projectIsOpen && <div className="cv-project-tree__children">{items.slice(0, showAllConversations ? undefined : 5).map(item => conversationList([item], true))}{items.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllProjectConversations(current => ({...current, [projectRef]: !current[projectRef]}))}>{showAllConversations ? 'Mostrar menos' : 'Mostrar mais'}</button>}{!items.length && <small>Sem chats</small>}</div>}
              </section>;
            })}{relatedProjects.length > 6 && <button type="button" className="cv-project-tree__more" onClick={() => setShowMoreBrandProjects(current => ({...current, [ref]: !current[ref]}))}>{showMoreBrandProjects[ref] ? 'Mostrar menos' : 'Mostrar mais'}</button>}{!relatedProjects.length && <small>Sem projetos vinculados</small>}</div>}
          </section>;
        })}{brandItems.length > 5 && <button type="button" className="cv-project-tree__more cv-brand-tree__more" onClick={() => setShowAllBrands(value => !value)}>{showAllBrands ? 'Mostrar menos' : 'Mostrar mais'}</button>}</section>}
        <section className="cv-nav-group cv-project-tree" aria-label="Projetos"><header><span>Projetos</span><b>{projectItems.length}</b></header>{projectItems.slice(0, showMoreProjects ? 10 : 6).map(project => { const ref = String(project.ref || project.projectRef || project.id); const isOpen = expandedProjects.has(ref); const items = filtered.filter(item => String(item.project_ref || '') === ref && item.section !== 'automation'); const showAll = Boolean(showAllProjectConversations[ref]); const projectName = project.name || project.title || 'Projeto'; const projectUrl = `/projetos/${encodeURIComponent(String(project.id || ref).replace(/^ci:/,''))}`; const selected = ref === String(activeProjectRef); return <section key={ref} className={`cv-project-tree__item${isOpen ? ' is-open' : ''}${selected ? ' is-active' : ''}`}><div className="cv-project-tree__heading"><button type="button" className="cv-project-tree__trigger" aria-expanded={isOpen} aria-current={selected ? 'location' : undefined} onClick={() => { toggleProject(ref); if (!selected) onProjectChange?.(ref); }}><NavIcon name={isOpen ? 'folderOpen' : 'folder'}/><SidebarTitle className="cv-project-tree__name">{projectName}</SidebarTitle></button><div className={`cv-project-menu${projectMenuId === ref ? ' is-open' : ''}`}><button type="button" className="cv-project-menu__trigger" aria-label={`Mais ações para ${projectName}`} aria-expanded={projectMenuId === ref} onClick={event => { event.stopPropagation(); setProjectMenuId(current => current === ref ? '' : ref); }}><span aria-hidden="true">…</span></button>{projectMenuId === ref && <div className="cv-project-menu__popover"><a href={projectUrl}><NavIcon name="folderOpen"/><span>Abrir projeto</span></a><button type="button" onClick={() => { setProjectMenuId(''); startProjectConversation(ref); }}><Icon name="newChat" size={16}/><span>Nova conversa</span></button><button type="button" onClick={() => { setProjectMenuId(''); openIndex(ref); }}><NavIcon name="library"/><span>Abrir arquivos</span></button></div>}</div></div>{isOpen && <div className="cv-project-tree__children">{items.slice(0, showAll ? undefined : 5).map(item => conversationList([item], true))}{items.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllProjectConversations(current => ({...current, [ref]: !current[ref]}))}>{showAll ? 'Mostrar menos' : 'Mostrar mais'}</button>}{!items.length && <small>Sem chats</small>}</div>}</section>; })}{projectItems.length > 6 && <button type="button" className="cv-project-tree__more" onClick={() => setShowMoreProjects(value => !value)}>{showMoreProjects ? 'Mostrar menos' : 'Mostrar mais'}</button>}</section>
        {activeBrand && <section className="cv-nav-group is-brand-context"><header><NavIcon name="folderOpen"/><span>{activeBrand.name}</span></header>{conversationList(brandConversations.slice(0, showAllRecent ? undefined : 5), true)}{brandConversations.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Mostrar mais'}</button>}</section>}
        <section className="cv-nav-group cv-personal-recent"><header><span>Recentes</span></header>{conversationList(standard.slice(0, showAllRecent ? undefined : 5), true)}{standard.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Mostrar mais'}</button>}{loading && !conversations.length && <div className="cv-recent-loading"><i/><i/><i/></div>}{!loading && !standard.length && <p>Nenhuma conversa recente.</p>}</section>
      </div>
      <footer className="cv-chat-sidebar-footer">{navUrls.profile ? <a href={navUrls.profile} aria-label={`Perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></a> : <button type="button" aria-label={`Abrir perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></button>}<UsageMiniChart percent={usagePercent}/></footer>
      </div>
      </>}
    </aside>
    {spotlightOpen && createPortal(<div className="cv-project-spotlight" onMouseDown={event => { if (event.target === event.currentTarget) setSpotlightOpen(false); }}><section role="dialog" aria-modal="true" aria-labelledby="cv-project-spotlight-title" className="cv-project-spotlight__panel"><header><div><small>{projectId ? 'BUSCA NO PROJETO' : 'BUSCA NAS CONVERSAS'}</small><h2 id="cv-project-spotlight-title">{activeProject?.name || activeProject?.title || 'Conversas'}</h2></div><button type="button" onClick={() => setSpotlightOpen(false)} aria-label="Fechar busca"><NavIcon name="close"/></button></header><label className="cv-project-spotlight__input"><NavIcon name="search"/><input ref={spotlightInput} value={spotlightQuery} onChange={event => setSpotlightQuery(event.target.value)} placeholder={projectId ? 'Buscar arquivos, tarefas, atividades…' : 'Buscar conversas…'} aria-label={projectId ? 'Buscar nos itens do projeto' : 'Buscar conversas'}/><kbd>ESC</kbd></label><div className="cv-project-spotlight__results" aria-live="polite">{spotlightQuery.trim().length < 2 ? <p>Digite pelo menos 2 caracteres para iniciar a busca.</p> : spotlightLoading ? <p>Pesquisando…</p> : spotlightError ? <p role="alert">{spotlightError}</p> : spotlightResults.length ? spotlightResults.map(item => item.kind === 'resource' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); if (onOpenLibraryRef) onOpenLibraryRef(`resource:${item.id}`, activeProjectRef).catch(error => { setSpotlightError(error.message || 'Não foi possível abrir este recurso.'); setSpotlightOpen(true); }); else onOpenResource?.({...item, libraryRef:`resource:${item.id}`, project_ref:activeProjectRef}); }}><NavIcon name="file"/><span><b>{item.title}</b><small>{item.detail || 'Recurso do projeto'}</small></span><NavIcon name="chevron"/></button> : item.kind === 'conversation' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); onOpen(String(item.id), item.title); }}><NavIcon name="compose"/><span><b>{item.title}</b><small>{item.detail || 'Conversa do projeto'}</small></span><NavIcon name="chevron"/></button> : <a key={`${item.kind}-${item.id}`} href={item.kind === 'task' ? projectTasksUrl : projectActivityUrl}><NavIcon name={item.kind === 'task' ? 'check' : 'pulse'}/><span><b>{item.title}</b><small>{item.detail || 'Atividade do projeto'}</small></span><NavIcon name="chevron"/></a>) : <p>Nenhum item encontrado{projectId ? ' neste projeto' : ''}.</p>}</div>{projectId && <footer>Arquivos · documentos · tarefas · atividade</footer>}</section></div>, document.getElementById('cadu-conversations-v2-root') || document.body)}
  </>;
}
