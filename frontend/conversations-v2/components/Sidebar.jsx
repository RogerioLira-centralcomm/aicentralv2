import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {request} from '../lib/api';
import {conversationDisplayTitle} from '../lib/conversationPresentation.mjs';
import {workspaceMobileDestinationItems, workspaceMobileSolutionItems} from '../../cadu-design-system/workspaceSolutions';
import {CaduSolutionSwitcher} from '../../cadu-design-system/components/WorkspaceSelectors';
import {VisualIdentity} from '../../cadu-design-system/components/VisualIdentity';
import {DockUsageRing} from '../../cadu-design-system/components/CaduDock';

function contextLabel(item, projects, brands) {
  const project = projects.find(candidate => (candidate.ref || candidate.projectRef || candidate.id) === item.project_ref);
  if (project) return project.name;
  const brand = brands.find(candidate => (candidate.ref || candidate.brandRef || `studio:${candidate.id}`) === item.brand_ref);
  return brand ? brand.name : '';
}

function NavIcon({name}) {
  return <span className={`cv-nav-icon is-${name}`} aria-hidden="true"/>;
}

export function Sidebar({conversations, projects = [], brands = [], activeProjectRef = '', activeBrandRef = '', navUrls = {}, solutions = [], logo, user = {}, usagePercent = 0, activeId, currentTitle = '', onOpen, onOpenLibrary, onOpenResource, onOpenLibraryRef, onNewConversation, onProjectChange, onOrganize, onConversationAction, open, onClose, loading, openingId}) {
  const sidebarRef = useRef(null);
  const previousFocus = useRef(null);
  const [showAllRecent, setShowAllRecent] = useState(false);
  const [showAllProjectConversations, setShowAllProjectConversations] = useState({});
  const [expandedProjects, setExpandedProjects] = useState(() => new Set(activeProjectRef ? [String(activeProjectRef)] : []));
  const [manuallyCollapsedProjects, setManuallyCollapsedProjects] = useState(() => new Set());
  const [collapsed, setCollapsed] = useState(false);
  const [actionMenuId, setActionMenuId] = useState('');
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [spotlightQuery, setSpotlightQuery] = useState('');
  const [spotlightResults, setSpotlightResults] = useState([]);
  const [spotlightLoading, setSpotlightLoading] = useState(false);
  const [spotlightError, setSpotlightError] = useState('');
  const spotlightInput = useRef(null);
  const searchSequence = useRef(0);
  const ordered = useMemo(() => {
    const active = String(activeProjectRef || '');
    if (!active) return conversations;
    return [...conversations].sort((left, right) => {
      const leftActive = String(left.project_ref || '') === active;
      const rightActive = String(right.project_ref || '') === active;
      return Number(rightActive) - Number(leftActive);
    });
  }, [conversations, activeProjectRef]);
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

  if (!open) return null;
  const projectConversations = filtered.filter(item => String(item.project_ref || '') === String(activeProjectRef));
  const brandConversations = filtered.filter(item => String(item.brand_ref || '') === String(activeBrandRef) && !['pinned', 'automation'].includes(item.section));
  const pinned = filtered.filter(item => item.section === 'pinned');
  const automations = filtered.filter(item => item.section === 'automation' && item.automation_enabled);
  const standard = filtered.filter(item => !item.project_ref && !item.brand_ref && !['pinned', 'automation'].includes(item.section));
  const activeConversation = conversations.find(item => String(item.id) === String(activeId));
  const mobileDestinations = workspaceMobileDestinationItems(navUrls);
  const mobileSolutions = workspaceMobileSolutionItems(navUrls);
  const projectItems = [...projects].sort((left, right) => Number(String(right.ref || right.projectRef || right.id) === String(activeProjectRef)) - Number(String(left.ref || left.projectRef || left.id) === String(activeProjectRef)));
  useEffect(() => { if (activeProjectRef) { const ref = String(activeProjectRef); setExpandedProjects(current => new Set([...current, ref])); setManuallyCollapsedProjects(current => { const next = new Set(current); next.delete(ref); return next; }); } }, [activeProjectRef]);
  const toggleProject = ref => {
    const key = String(ref);
    setExpandedProjects(current => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
    setManuallyCollapsedProjects(current => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  };
  const openIndex = ref => { if (ref || activeProjectRef) onOpenLibrary?.(true, ref || activeProjectRef); else setSpotlightError('Selecione um projeto para abrir o Indexador.'); };
  const runAction = (event, item, action) => {
    event.stopPropagation();
    setActionMenuId('');
    onConversationAction?.(item, action);
  };
  const conversationList = (items, hideContext = false) => items.map(item => { const context = contextLabel(item, projects, brands); return <div className="cv-conversation-row" key={item.id} draggable onDragStart={event => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('application/x-cadu-conversation', String(item.id)); }}>
    <button className="cv-conversation-card" type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={conversationDisplayTitle(item.title, 'Chat sem título')}><span className="cv-conversation-card__copy"><b>{conversationDisplayTitle(item.title, 'Chat sem título')}</b>{!hideContext && <small><NavIcon name={context ? 'folder' : 'compose'}/>{context || 'Sessão livre'}</small>}</span><span className={`cv-conversation-card__state ${item.running ? 'is-running' : ''}${item.awaiting_response ? ' is-awaiting-response' : ''}`} title={item.running ? 'Processo em andamento' : item.awaiting_response ? 'Aguardando sua resposta' : item.section === 'automation' && item.automation_enabled ? 'Automação agendada' : ''}>{item.running ? <i/> : item.awaiting_response || (item.section === 'automation' && item.automation_enabled) ? <NavIcon name="clock"/> : null}</span></button>
    <div className={`cv-conversation-actions ${String(actionMenuId) === String(item.id) ? 'is-open' : ''}`}>
      <button type="button" className="cv-conversation-actions__trigger" aria-label={`Ações de ${item.title || 'conversa'}`} aria-expanded={String(actionMenuId) === String(item.id)} onClick={event => { event.stopPropagation(); setActionMenuId(current => String(current) === String(item.id) ? '' : String(item.id)); }}><span aria-hidden="true">•••</span></button>
      {String(actionMenuId) === String(item.id) && <div className="cv-conversation-actions__menu" role="menu">
        <button type="button" role="menuitem" onClick={event => runAction(event, item, 'toggle-pin')}>{item.section === 'pinned' ? 'Desafixar' : 'Fixar conversa'}</button>
        {item.section === 'automation' && item.automation_enabled && <button type="button" role="menuitem" onClick={event => runAction(event, item, 'stop-automation')}>Encerrar automação</button>}
        <button type="button" role="menuitem" className="is-danger" onClick={event => runAction(event, item, 'archive')}>Arquivar</button>
      </div>}
    </div>
  </div>; });
  const handleDrop = (event, section) => {
    if (!event.dataTransfer.types.includes('application/x-cadu-conversation')) return;
    event.preventDefault();
    const id = event.dataTransfer.getData('application/x-cadu-conversation');
    if (id) onOrganize?.(id, section);
  };
  const dropSection = (section, label, items) => <section className={`cv-conversation-section is-${section}${section === 'pinned' ? ' is-drop-target' : ''}`} onDragOver={event => { if (event.dataTransfer.types.includes('application/x-cadu-conversation')) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; event.currentTarget.classList.add('is-drag-over'); } }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.classList.remove('is-drag-over'); }} onDrop={event => { event.currentTarget.classList.remove('is-drag-over'); handleDrop(event, section); }}><header><span>{label}</span><b>{items.length || ''}</b></header>{items.length ? conversationList(items) : section === 'pinned' ? <p className="cv-drop-hint">Arraste uma conversa para fixar</p> : null}</section>;
  return <>
    <button type="button" onClick={onClose} aria-label="Fechar chats recentes" className="cv-recent-backdrop is-visible"/>
    <aside ref={sidebarRef} id="cv-recent-sidebar" role={window.matchMedia('(max-width: 767px)').matches ? 'dialog' : undefined} aria-modal={window.matchMedia('(max-width: 767px)').matches ? 'true' : undefined} className={`cv-recent-sidebar is-open${collapsed ? ' is-collapsed' : ''}`} aria-label="Chats recentes">
      <div className="cv-mobile-navigation">
        <header><div><strong>Workspace</strong><small>{conversationDisplayTitle(currentTitle || activeConversation?.title, 'Novo chat')}</small></div><button type="button" onClick={onClose} aria-label="Fechar navegação"><NavIcon name="close"/></button></header>
        <div className="cv-mobile-navigation__scroll">
          <button type="button" className="cv-mobile-navigation__primary" onClick={onNewConversation}>Novo chat</button>
          {activeProject && projectDetailsUrl && <a className="cv-mobile-navigation__project-link" href={projectDetailsUrl} onClick={onClose}><NavIcon name="folder"/><span>{activeProject.name || activeProject.title}</span></a>}
          <div className="cv-sidebar-project-tools"><button type="button" title="Buscar no projeto" aria-label="Buscar no projeto" onClick={() => { setSpotlightQuery(''); setSpotlightOpen(true); }}><NavIcon name="search"/></button></div>
          <section><h2>Conversas fixadas</h2>{conversationList(pinned.slice(0, 5))}</section>
          {!!automations.length && <section><h2>Automações</h2>{conversationList(automations.slice(0, 5))}</section>}
          <section><h2>Chats recentes</h2>{conversationList(standard.slice(0, 5))}{standard.length > 5 && <button type="button" className="cv-mobile-navigation__more" onClick={event => { event.currentTarget.closest('section')?.classList.add('is-expanded'); }}>Ver todos</button>}{standard.length > 5 && <div className="cv-mobile-navigation__extra">{conversationList(standard.slice(5))}</div>}</section>
          {!!mobileDestinations.length && <nav className="cv-mobile-navigation__destinations" aria-label="Áreas do Workspace"><h2>Workspace</h2>{mobileDestinations.map(item => <a key={item.id} href={item.href} onClick={onClose}><NavIcon name={item.icon}/><span>{item.name}</span></a>)}</nav>}
          {!!mobileSolutions.length && <nav className="cv-mobile-navigation__solutions" aria-label="Outras soluções"><h2>Outras soluções</h2>{mobileSolutions.map(item => <a key={item.id} href={item.href} onClick={onClose}><span><b>{item.name}</b><small>{item.description}</small></span></a>)}</nav>}
          {navUrls.profile && <nav className="cv-mobile-navigation__account" aria-label="Conta"><a href={navUrls.profile} onClick={onClose}><NavIcon name="brand"/><span>Conta e configurações</span></a></nav>}
        </div>
      </div>
      <div className={`cv-desktop-history${collapsed ? ' is-collapsed' : ''}`}>
      <header className="cv-recent-sidebar__header">
        <div className="cv-chat-solution-switcher"><CaduSolutionSwitcher logo={logo} solutions={solutions} activeId="workspace"/><span aria-current="page">Chat</span></div>
        <div className="cv-recent-sidebar__tools"><button type="button" className="cv-sidebar-icon-button" onClick={() => { setSpotlightQuery(''); setSpotlightOpen(true); }} aria-label="Buscar conversas" title="Buscar conversas"><NavIcon name="search"/></button><button type="button" className="cv-sidebar-icon-button" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? 'Expandir sidebar' : 'Recolher sidebar'} title={collapsed ? 'Expandir' : 'Recolher'}><NavIcon name={collapsed ? 'expand' : 'collapse'}/></button></div>
      </header>
      <div className="cv-recent-list">
        <button className="cv-nav-action" type="button" onClick={onNewConversation}><NavIcon name="compose"/><span>Novo chat</span></button>
        <section className="cv-nav-group is-scheduled"><header><NavIcon name="clock"/><span>Agendado</span><b>{automations.length || ''}</b></header>{automations.length ? conversationList(automations) : <p>Conversas e execuções programadas aparecem aqui.</p>}</section>
        <a className="cv-nav-action" href={navUrls.plugins || navUrls.solutions?.connect || '#'}><NavIcon name="plugin"/><span>Plugins</span></a>
        <button className="cv-nav-action" type="button" onClick={() => openIndex(activeProjectRef)}><NavIcon name="library"/><span>Indexador</span></button>
        {dropSection('pinned', 'Conversas fixadas', pinned)}
        <section className="cv-nav-group cv-project-tree" aria-label="Projetos"><header><NavIcon name="folder"/><span>Projetos</span></header>{projectItems.map(project => { const ref = String(project.ref || project.projectRef || project.id); const isOpen = expandedProjects.has(ref); const items = filtered.filter(item => String(item.project_ref || '') === ref && !['pinned','automation'].includes(item.section)); const showAll = Boolean(showAllProjectConversations[ref]); return <section key={ref} className={`cv-project-tree__item${isOpen ? ' is-open' : ''}${ref === String(activeProjectRef) ? ' is-active' : ''}`}><button type="button" className="cv-project-tree__trigger" aria-expanded={isOpen} aria-current={ref === String(activeProjectRef) ? 'location' : undefined} onClick={() => { toggleProject(ref); if (ref !== String(activeProjectRef)) onProjectChange?.(ref); }}><NavIcon name={isOpen ? 'folderOpen' : 'folder'}/><span>{project.name || project.title}</span></button>{isOpen && <div className="cv-project-tree__children"><div className="cv-project-tree__tools"><button type="button" onClick={() => openIndex(ref)}>Indexador</button><a href={`/projetos/${encodeURIComponent(String(project.id || ref).replace(/^ci:/,''))}`} aria-label={`Abrir projeto ${project.name || project.title}`}>Abrir projeto</a></div>{items.slice(0, showAll ? undefined : 5).map(item => conversationList([item], true))}{items.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllProjectConversations(current => ({...current, [ref]: !current[ref]}))}>{showAll ? 'Mostrar menos' : 'Mostrar mais'}</button>}{!items.length && <small>Sem chats</small>}</div>}</section>; })}</section>
        {activeBrand && <section className="cv-nav-group is-brand-context"><header><NavIcon name="folderOpen"/><span>{activeBrand.name}</span></header>{conversationList(brandConversations.slice(0, showAllRecent ? undefined : 5), true)}{brandConversations.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Mostrar mais'}</button>}</section>}
        <section className="cv-nav-group cv-personal-recent"><header><NavIcon name="chat"/><span>Recentes</span></header>{conversationList(standard.slice(0, showAllRecent ? undefined : 5), true)}{standard.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Mostrar mais'}</button>}{loading && !conversations.length && <div className="cv-recent-loading"><i/><i/><i/></div>}{!loading && !standard.length && <p>Nenhuma conversa recente.</p>}</section>
      </div>
      <footer className="cv-chat-sidebar-footer"><DockUsageRing percent={usagePercent} href={navUrls.usage || navUrls.credits}/>{navUrls.profile ? <a href={navUrls.profile} aria-label={`Perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></a> : <button type="button" aria-label={`Abrir perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></button>}</footer>
      </div>
    </aside>
    {spotlightOpen && createPortal(<div className="cv-project-spotlight" onMouseDown={event => { if (event.target === event.currentTarget) setSpotlightOpen(false); }}><section role="dialog" aria-modal="true" aria-labelledby="cv-project-spotlight-title" className="cv-project-spotlight__panel"><header><div><small>{projectId ? 'BUSCA NO PROJETO' : 'BUSCA NAS CONVERSAS'}</small><h2 id="cv-project-spotlight-title">{activeProject?.name || activeProject?.title || 'Conversas'}</h2></div><button type="button" onClick={() => setSpotlightOpen(false)} aria-label="Fechar busca"><NavIcon name="close"/></button></header><label className="cv-project-spotlight__input"><NavIcon name="search"/><input ref={spotlightInput} value={spotlightQuery} onChange={event => setSpotlightQuery(event.target.value)} placeholder={projectId ? 'Buscar arquivos, tarefas, atividades…' : 'Buscar conversas…'} aria-label={projectId ? 'Buscar nos itens do projeto' : 'Buscar conversas'}/><kbd>ESC</kbd></label><div className="cv-project-spotlight__results" aria-live="polite">{spotlightQuery.trim().length < 2 ? <p>Digite pelo menos 2 caracteres para iniciar a busca.</p> : spotlightLoading ? <p>Pesquisando…</p> : spotlightError ? <p role="alert">{spotlightError}</p> : spotlightResults.length ? spotlightResults.map(item => item.kind === 'resource' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); if (onOpenLibraryRef) onOpenLibraryRef(`resource:${item.id}`, activeProjectRef).catch(error => { setSpotlightError(error.message || 'Não foi possível abrir este recurso.'); setSpotlightOpen(true); }); else onOpenResource?.({...item, libraryRef:`resource:${item.id}`, project_ref:activeProjectRef}); }}><NavIcon name="file"/><span><b>{item.title}</b><small>{item.detail || 'Recurso do projeto'}</small></span><NavIcon name="chevron"/></button> : item.kind === 'conversation' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); onOpen(String(item.id), item.title); }}><NavIcon name="compose"/><span><b>{item.title}</b><small>{item.detail || 'Conversa do projeto'}</small></span><NavIcon name="chevron"/></button> : <a key={`${item.kind}-${item.id}`} href={item.kind === 'task' ? projectTasksUrl : projectActivityUrl}><NavIcon name={item.kind === 'task' ? 'check' : 'pulse'}/><span><b>{item.title}</b><small>{item.detail || 'Atividade do projeto'}</small></span><NavIcon name="chevron"/></a>) : <p>Nenhum item encontrado{projectId ? ' neste projeto' : ''}.</p>}</div>{projectId && <footer>Arquivos · documentos · tarefas · atividade</footer>}</section></div>, document.getElementById('cadu-conversations-v2-root') || document.body)}
  </>;
}
