import React, {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {request} from '../lib/api';
import {conversationDisplayTitle} from '../lib/conversationPresentation.mjs';
import {workspaceMobileDestinationItems, workspaceMobileSolutionItems} from '../../cadu-design-system/workspaceSolutions';
import {CaduSolutionSwitcher} from '../../cadu-design-system/components/WorkspaceSelectors';
import {VisualIdentity} from '../../cadu-design-system/components/VisualIdentity';
import {DockUsageRing} from '../../cadu-design-system/components/CaduDock';
import {Icon} from '../../cadu-design-system/components/Icon';
import {CaduDialog} from '../../cadu-design-system/components/CaduDialog';
import {useWorkspaceNotifications} from '../../cadu-design-system/components/WorkspaceNotifications';

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

export function Sidebar({conversations, projects = [], brands = [], activeProjectRef = '', activeBrandRef = '', navUrls = {}, solutions = [], logo, user = {}, usagePercent = 0, activeId, currentTitle = '', onOpen, onOpenLibrary, onOpenResource, onOpenLibraryRef, onNewConversation, onProjectChange, onConversationAction, open, onOpenSidebar, onClose, loading, openingId}) {
  const sidebarRef = useRef(null);
  const previousFocus = useRef(null);
  const [showAllRecent, setShowAllRecent] = useState(false);
  const [showAllProjectConversations, setShowAllProjectConversations] = useState({});
  const [expandedProjects, setExpandedProjects] = useState(() => new Set(activeProjectRef ? [String(activeProjectRef)] : []));
  const [projectMenuId, setProjectMenuId] = useState('');
  const [actionMenuId, setActionMenuId] = useState('');
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [pluginTools, setPluginTools] = useState([]);
  const [pluginToolsLoading, setPluginToolsLoading] = useState(false);
  const [pluginToolsError, setPluginToolsError] = useState('');
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
    if (!pluginsOpen) return undefined;
    let current = true;
    setPluginToolsLoading(true);
    setPluginToolsError('');
    request('/workspace/api/v2/capabilities')
      .then(data => { if (current) setPluginTools(Array.isArray(data.tools) ? data.tools : []); })
      .catch(error => { if (current) setPluginToolsError(error.message || 'Não foi possível carregar os plugins disponíveis.'); })
      .finally(() => { if (current) setPluginToolsLoading(false); });
    return () => { current = false; };
  }, [pluginsOpen]);

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

  if (!open && !desktopMode) return null;
  const brandConversations = filtered.filter(item => String(item.brand_ref || '') === String(activeBrandRef) && item.section !== 'automation');
  const automations = filtered.filter(item => item.section === 'automation' && item.automation_enabled);
  const standard = filtered.filter(item => !item.project_ref && !item.brand_ref && item.section !== 'automation');
  const activeConversation = conversations.find(item => String(item.id) === String(activeId));
  const mobileDestinations = workspaceMobileDestinationItems(navUrls);
  const mobileSolutions = workspaceMobileSolutionItems(navUrls);
  const projectItems = [...projects].sort((left, right) => String(left.name || left.title || '').localeCompare(String(right.name || right.title || ''), 'pt-BR', {sensitivity: 'base'}));
  const toggleProject = ref => {
    const key = String(ref);
    setExpandedProjects(current => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
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
    <button className="cv-conversation-card" type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={conversationDisplayTitle(item.title, 'Chat sem título')}><span className="cv-conversation-card__copy"><b><SidebarTitle>{conversationDisplayTitle(item.title, 'Chat sem título')}</SidebarTitle></b>{!hideContext && <small><NavIcon name={context ? 'folder' : 'compose'}/>{context || 'Sessão livre'}</small>}</span><span className={`cv-conversation-card__state ${item.running ? 'is-running' : ''}${item.awaiting_response ? ' is-awaiting-response' : ''}`} title={item.running ? 'Processo em andamento' : item.awaiting_response ? 'Aguardando sua resposta' : item.section === 'automation' && item.automation_enabled ? 'Automação agendada' : ''}>{item.running ? <i/> : item.awaiting_response || (item.section === 'automation' && item.automation_enabled) ? <NavIcon name="clock"/> : null}</span></button>
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
        <div className="cv-sidebar-mini-rail__top"><CaduSolutionSwitcher logo={logo} solutions={solutions} activeId="workspace"/><button type="button" className="cv-sidebar-icon-button" onClick={onOpenSidebar} aria-label="Abrir navegação do chat" title="Abrir navegação"><NavIcon name="expand"/></button></div>
        <div className="cv-sidebar-mini-rail__bottom"><DockUsageRing percent={usagePercent} href={navUrls.usage || navUrls.credits}/>{navUrls.profile ? <a href={navUrls.profile} aria-label={`Perfil de ${user.name || 'usuário'}`} title={user.name || 'Perfil'}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/></a> : <button type="button" aria-label={`Abrir perfil de ${user.name || 'usuário'}`} title={user.name || 'Perfil'}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/></button>}</div>
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
        {navUrls.home && <a className="cv-nav-action" href={navUrls.home}><Icon name="home" size={17}/><span>Início</span></a>}
        <button className="cv-nav-action" type="button" onClick={onNewConversation}><Icon name="newChat" size={17}/><span>Novo chat</span></button>
        <section className="cv-nav-group is-scheduled"><header><NavIcon name="clock"/><span>Agendado</span><b>{automations.length || ''}</b></header>{automations.length ? conversationList(automations) : null}</section>
        <button className="cv-nav-action" type="button" onClick={() => setPluginsOpen(true)}><NavIcon name="plugin"/><span>Plugins</span></button>
        <button className="cv-nav-action" type="button" onClick={() => openIndex(activeProjectRef)}><NavIcon name="library"/><span>Arquivos</span></button>
        <section className="cv-nav-group cv-project-tree" aria-label="Projetos"><header><span>Projetos</span></header>{projectItems.map(project => { const ref = String(project.ref || project.projectRef || project.id); const isOpen = expandedProjects.has(ref); const items = filtered.filter(item => String(item.project_ref || '') === ref && item.section !== 'automation'); const showAll = Boolean(showAllProjectConversations[ref]); const projectName = project.name || project.title || 'Projeto'; const projectUrl = `/projetos/${encodeURIComponent(String(project.id || ref).replace(/^ci:/,''))}`; return <section key={ref} className={`cv-project-tree__item${isOpen ? ' is-open' : ''}${ref === String(activeProjectRef) ? ' is-active' : ''}`}><div className="cv-project-tree__heading"><button type="button" className="cv-project-tree__trigger" aria-expanded={isOpen} aria-current={ref === String(activeProjectRef) ? 'location' : undefined} onClick={() => { toggleProject(ref); if (ref !== String(activeProjectRef)) onProjectChange?.(ref); }}><NavIcon name={isOpen ? 'folderOpen' : 'folder'}/><SidebarTitle className="cv-project-tree__name">{projectName}</SidebarTitle></button><div className={`cv-project-menu${projectMenuId === ref ? ' is-open' : ''}`}><button type="button" className="cv-project-menu__trigger" aria-label={`Mais ações para ${projectName}`} aria-expanded={projectMenuId === ref} onClick={event => { event.stopPropagation(); setProjectMenuId(current => current === ref ? '' : ref); }}><span aria-hidden="true">…</span></button>{projectMenuId === ref && <div className="cv-project-menu__popover"><a href={projectUrl}><NavIcon name="folderOpen"/><span>Abrir projeto</span></a><button type="button" onClick={() => { setProjectMenuId(''); startProjectConversation(ref); }}><Icon name="newChat" size={16}/><span>Nova conversa</span></button><button type="button" onClick={() => { setProjectMenuId(''); openIndex(ref); }}><NavIcon name="library"/><span>Abrir arquivos</span></button></div>}</div></div>{isOpen && <div className="cv-project-tree__children">{items.slice(0, showAll ? undefined : 5).map(item => conversationList([item], true))}{items.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllProjectConversations(current => ({...current, [ref]: !current[ref]}))}>{showAll ? 'Mostrar menos' : 'Mostrar mais'}</button>}{!items.length && <small>Sem chats</small>}</div>}</section>; })}</section>
        {activeBrand && <section className="cv-nav-group is-brand-context"><header><NavIcon name="folderOpen"/><span>{activeBrand.name}</span></header>{conversationList(brandConversations.slice(0, showAllRecent ? undefined : 5), true)}{brandConversations.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Mostrar mais'}</button>}</section>}
        <section className="cv-nav-group cv-personal-recent"><header><span>Recentes</span></header>{conversationList(standard.slice(0, showAllRecent ? undefined : 5), true)}{standard.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Mostrar mais'}</button>}{loading && !conversations.length && <div className="cv-recent-loading"><i/><i/><i/></div>}{!loading && !standard.length && <p>Nenhuma conversa recente.</p>}</section>
      </div>
      <footer className="cv-chat-sidebar-footer">{navUrls.profile ? <a href={navUrls.profile} aria-label={`Perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></a> : <button type="button" aria-label={`Abrir perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></button>}<UsageMiniChart percent={usagePercent}/></footer>
      </div>
      </>}
    </aside>
    {pluginsOpen && <CaduDialog className="cv-plugins-dialog" label="Plugins" closeOnBackdrop onClose={() => setPluginsOpen(false)}><header><div><h2>Plugins</h2><p>Ferramentas disponíveis para usar nesta conversa.</p></div><button type="button" onClick={() => setPluginsOpen(false)} aria-label="Fechar plugins">×</button></header><div className="cv-plugins-dialog__content" aria-live="polite">{pluginToolsLoading ? <p>Carregando ferramentas…</p> : pluginToolsError ? <p role="alert">{pluginToolsError}</p> : pluginTools.length ? <ul>{pluginTools.map((tool, index) => <li key={tool.name || tool.id || index}><span className="cv-plugins-dialog__icon"><NavIcon name="plugin"/></span><span><strong>{tool.title || tool.name || tool.id || 'Ferramenta'}</strong><small>{tool.description || tool.summary || 'Disponível nesta conversa.'}</small></span></li>)}</ul> : <p>Nenhum plugin está conectado a esta conversa.</p>}</div>{(navUrls.plugins || navUrls.solutions?.connect) && <footer><a href={navUrls.plugins || navUrls.solutions?.connect}>Explorar conexões</a></footer>}</CaduDialog>}
    {spotlightOpen && createPortal(<div className="cv-project-spotlight" onMouseDown={event => { if (event.target === event.currentTarget) setSpotlightOpen(false); }}><section role="dialog" aria-modal="true" aria-labelledby="cv-project-spotlight-title" className="cv-project-spotlight__panel"><header><div><small>{projectId ? 'BUSCA NO PROJETO' : 'BUSCA NAS CONVERSAS'}</small><h2 id="cv-project-spotlight-title">{activeProject?.name || activeProject?.title || 'Conversas'}</h2></div><button type="button" onClick={() => setSpotlightOpen(false)} aria-label="Fechar busca"><NavIcon name="close"/></button></header><label className="cv-project-spotlight__input"><NavIcon name="search"/><input ref={spotlightInput} value={spotlightQuery} onChange={event => setSpotlightQuery(event.target.value)} placeholder={projectId ? 'Buscar arquivos, tarefas, atividades…' : 'Buscar conversas…'} aria-label={projectId ? 'Buscar nos itens do projeto' : 'Buscar conversas'}/><kbd>ESC</kbd></label><div className="cv-project-spotlight__results" aria-live="polite">{spotlightQuery.trim().length < 2 ? <p>Digite pelo menos 2 caracteres para iniciar a busca.</p> : spotlightLoading ? <p>Pesquisando…</p> : spotlightError ? <p role="alert">{spotlightError}</p> : spotlightResults.length ? spotlightResults.map(item => item.kind === 'resource' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); if (onOpenLibraryRef) onOpenLibraryRef(`resource:${item.id}`, activeProjectRef).catch(error => { setSpotlightError(error.message || 'Não foi possível abrir este recurso.'); setSpotlightOpen(true); }); else onOpenResource?.({...item, libraryRef:`resource:${item.id}`, project_ref:activeProjectRef}); }}><NavIcon name="file"/><span><b>{item.title}</b><small>{item.detail || 'Recurso do projeto'}</small></span><NavIcon name="chevron"/></button> : item.kind === 'conversation' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); onOpen(String(item.id), item.title); }}><NavIcon name="compose"/><span><b>{item.title}</b><small>{item.detail || 'Conversa do projeto'}</small></span><NavIcon name="chevron"/></button> : <a key={`${item.kind}-${item.id}`} href={item.kind === 'task' ? projectTasksUrl : projectActivityUrl}><NavIcon name={item.kind === 'task' ? 'check' : 'pulse'}/><span><b>{item.title}</b><small>{item.detail || 'Atividade do projeto'}</small></span><NavIcon name="chevron"/></a>) : <p>Nenhum item encontrado{projectId ? ' neste projeto' : ''}.</p>}</div>{projectId && <footer>Arquivos · documentos · tarefas · atividade</footer>}</section></div>, document.getElementById('cadu-conversations-v2-root') || document.body)}
  </>;
}
