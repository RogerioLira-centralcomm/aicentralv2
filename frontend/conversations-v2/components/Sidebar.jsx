import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Icon} from '../lib/icons';
import {request} from '../lib/api';
import {conversationDisplayTitle} from '../lib/conversationPresentation.mjs';
import {workspaceMobileDestinationItems, workspaceMobileSolutionItems} from '../../cadu-design-system/workspaceSolutions';

function contextLabel(item, projects, brands) {
  const project = projects.find(candidate => (candidate.ref || candidate.projectRef || candidate.id) === item.project_ref);
  if (project) return project.name;
  const brand = brands.find(candidate => (candidate.ref || candidate.brandRef || `studio:${candidate.id}`) === item.brand_ref);
  return brand ? brand.name : '';
}

function TimerIcon() {
  return <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><circle cx="8" cy="9" r="5.25" fill="none" stroke="currentColor" strokeWidth="1.3"/><path d="M8 9V6.2M6.2 2.1h3.6M11.8 4.2l1-1" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>;
}

export function Sidebar({conversations, projects = [], brands = [], activeProjectRef = '', navUrls = {}, activeId, currentTitle = '', onOpen, onOpenLibrary, onOpenResource, onOpenLibraryRef, onNewConversation, onProjectChange, onOrganize, onConversationAction, open, onClose, loading, openingId}) {
  const sidebarRef = useRef(null);
  const previousFocus = useRef(null);
  const [showAllRecent, setShowAllRecent] = useState(false);
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
  const projectId = String(activeProject?.id || activeProjectRef || '').replace(/^ci:/, '');
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
  const projectConversations = filtered.filter(item => String(item.project_ref || '') === String(activeProjectRef)).slice(0, 10);
  const otherConversations = filtered.filter(item => String(item.project_ref || '') !== String(activeProjectRef) && !['pinned', 'automation'].includes(item.section));
  const pinned = filtered.filter(item => item.section === 'pinned');
  const automations = filtered.filter(item => item.section === 'automation');
  const standard = filtered.filter(item => !['pinned', 'automation'].includes(item.section));
  const activeConversation = conversations.find(item => String(item.id) === String(activeId));
  const mobileDestinations = workspaceMobileDestinationItems(navUrls);
  const mobileSolutions = workspaceMobileSolutionItems(navUrls);
  const runAction = (event, item, action) => {
    event.stopPropagation();
    setActionMenuId('');
    onConversationAction?.(item, action);
  };
  const conversationList = (items, hideContext = false) => items.map(item => { const context = contextLabel(item, projects, brands); return <div className="cv-conversation-row" key={item.id} draggable onDragStart={event => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('application/x-cadu-conversation', String(item.id)); }}>
    <button className="cv-conversation-card" type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={conversationDisplayTitle(item.title, 'Chat sem título')}><span className="cv-conversation-card__copy"><b>{conversationDisplayTitle(item.title, 'Chat sem título')}</b>{!hideContext && <small><Icon name={context ? 'folder' : 'compose'} size={11}/>{context || 'Sessão livre'}</small>}</span><span className={`cv-conversation-card__state ${item.running ? 'is-running' : ''}${item.awaiting_response ? ' is-awaiting-response' : ''}`} title={item.running ? 'Processo em andamento' : item.awaiting_response ? 'Aguardando sua resposta' : item.section === 'automation' && item.automation_enabled ? 'Automação agendada' : ''}>{item.running ? <i/> : item.awaiting_response || (item.section === 'automation' && item.automation_enabled) ? <TimerIcon/> : null}</span></button>
    <div className={`cv-conversation-actions ${String(actionMenuId) === String(item.id) ? 'is-open' : ''}`}>
      <button type="button" className="cv-conversation-actions__trigger" aria-label={`Ações de ${item.title || 'conversa'}`} aria-expanded={String(actionMenuId) === String(item.id)} onClick={event => { event.stopPropagation(); setActionMenuId(current => String(current) === String(item.id) ? '' : String(item.id)); }}><span aria-hidden="true">•••</span></button>
      {String(actionMenuId) === String(item.id) && <div className="cv-conversation-actions__menu" role="menu">
        <button type="button" role="menuitem" onClick={event => runAction(event, item, 'toggle-pin')}>{item.section === 'pinned' ? 'Desafixar' : 'Fixar conversa'}</button>
        {item.section === 'automation' && item.automation_enabled && <button type="button" role="menuitem" onClick={event => runAction(event, item, 'stop-automation')}>Encerrar automação</button>}
        <button type="button" role="menuitem" className="is-danger" onClick={event => runAction(event, item, 'archive')}>Arquivar</button>
      </div>}
    </div>
  </div>; });
  const dropSection = (section, label, items) => items.length ? <section className={`cv-conversation-section is-${section}`} onDragOver={event => { if (event.dataTransfer.types.includes('application/x-cadu-conversation')) event.preventDefault(); }} onDrop={event => { event.preventDefault(); const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, section); }}><header><span>{label}</span><b>{items.length || ''}</b></header>{conversationList(items)}</section> : null;
  return <>
    <button type="button" onClick={onClose} aria-label="Fechar chats recentes" className="cv-recent-backdrop is-visible"/>
    <aside ref={sidebarRef} id="cv-recent-sidebar" role={window.matchMedia('(max-width: 767px)').matches ? 'dialog' : undefined} aria-modal={window.matchMedia('(max-width: 767px)').matches ? 'true' : undefined} className="cv-recent-sidebar is-open" aria-label="Chats recentes">
      <div className="cv-mobile-navigation">
        <header><div><strong>Workspace</strong><small>{conversationDisplayTitle(currentTitle || activeConversation?.title, 'Novo chat')}</small></div><button type="button" onClick={onClose} aria-label="Fechar navegação"><Icon name="close" size={18}/></button></header>
        <div className="cv-mobile-navigation__scroll">
          <button type="button" className="cv-mobile-navigation__primary" onClick={onNewConversation}>Novo chat</button>
          <div className="cv-sidebar-project-tools"><button type="button" title="Buscar no projeto" aria-label="Buscar no projeto" onClick={() => { setSpotlightQuery(''); setSpotlightOpen(true); }}><Icon name="search" size={14}/></button>{projectActivityUrl && <a href={projectActivityUrl} title="Atividade do projeto" aria-label="Atividade do projeto"><Icon name="folder" size={14}/></a>}</div>
          <section><h2>Conversas fixadas</h2>{conversationList(pinned.slice(0, 5))}{!pinned.length && <p className="cv-mobile-navigation__empty">Fixe uma conversa pelo menu de ações para encontrá-la aqui.</p>}</section>
          {!!automations.length && <section><h2>Automações</h2>{conversationList(automations.slice(0, 5))}</section>}
          <section><h2>Chats recentes</h2>{conversationList(standard.slice(0, 5))}{standard.length > 5 && <button type="button" className="cv-mobile-navigation__more" onClick={event => { event.currentTarget.closest('section')?.classList.add('is-expanded'); }}>Ver todos</button>}{standard.length > 5 && <div className="cv-mobile-navigation__extra">{conversationList(standard.slice(5))}</div>}</section>
          {!!mobileDestinations.length && <nav className="cv-mobile-navigation__destinations" aria-label="Áreas do Workspace"><h2>Workspace</h2>{mobileDestinations.map(item => <a key={item.id} href={item.href} onClick={onClose}><Icon name={item.icon} size={17}/><span>{item.name}</span></a>)}</nav>}
          {!!mobileSolutions.length && <nav className="cv-mobile-navigation__solutions" aria-label="Outras soluções"><h2>Outras soluções</h2>{mobileSolutions.map(item => <a key={item.id} href={item.href} onClick={onClose}><span><b>{item.name}</b><small>{item.description}</small></span></a>)}</nav>}
          {navUrls.profile && <nav className="cv-mobile-navigation__account" aria-label="Conta"><a href={navUrls.profile} onClick={onClose}><Icon name="brand" size={17}/><span>Conta e configurações</span></a></nav>}
        </div>
      </div>
      <div className="cv-desktop-history">
      <header className="cv-recent-sidebar__header">
        <div><strong>Conversas recentes</strong>{activeProject && <span>{activeProject.name || activeProject.title}</span>}</div>
        <div className="cv-recent-sidebar__tools"><button type="button" className="cv-sidebar-icon-button" onClick={() => { setSpotlightQuery(''); setSpotlightOpen(true); }} aria-label="Buscar no projeto" title="Buscar no projeto"><Icon name="search" size={14}/></button>{projectActivityUrl && <a className="cv-sidebar-icon-button" href={projectActivityUrl} aria-label="Atividade do projeto" title="Atividade do projeto"><Icon name="folder" size={14}/></a>}<button type="button" className="cv-sidebar-icon-button" onClick={onClose} aria-label="Recolher chats recentes"><Icon name="chevron" size={15}/></button></div>
      </header>
      <div className="cv-recent-list">
        {dropSection('pinned', 'Conversas fixadas', pinned) || <section className="cv-conversation-section is-pinned"><header><span>Conversas fixadas</span></header><p className="cv-pinned-empty">Arraste uma conversa para cá ou fixe pelo menu de ações.</p></section>}
        {dropSection('automation', 'Automações', automations)}
        {activeProject && <section className="cv-recent-project-section" onDragOver={event => event.preventDefault()} onDrop={event => { const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, 'recent'); }}><header><span>Conversas</span><button type="button" className="cv-recent-new" onClick={onNewConversation}><Icon name="plus" size={12}/>Nova</button></header>{conversationList(projectConversations.filter(item => !['pinned', 'automation'].includes(item.section)), true)}{!loading && !projectConversations.some(item => !['pinned', 'automation'].includes(item.section)) && <p>Ainda não há conversas deste projeto.</p>}</section>}
            {!activeProject && <section className="cv-recent-project-section" onDragOver={event => event.preventDefault()} onDrop={event => { const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, 'recent'); }}><header><span>Mais recentes</span><b>{standard.length || ''}</b></header>{conversationList(standard.slice(0, showAllRecent ? undefined : 10))}{standard.length > 10 && <button type="button" className="cv-recent-show-all" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Ver todas'}</button>}{loading && !conversations.length && <div className="cv-recent-loading" aria-label="Carregando conversas"><i/><i/><i/></div>}{!loading && !filtered.length && <p>Nenhuma conversa recente.</p>}</section>}
        {activeProject && <details className="cv-recent-all-section"><summary>Outras conversas <b>{otherConversations.length}</b></summary><div>{conversationList(otherConversations.slice(0, 8))}</div></details>}
      </div>
      </div>
    </aside>
    {spotlightOpen && createPortal(<div className="cv-project-spotlight" onMouseDown={event => { if (event.target === event.currentTarget) setSpotlightOpen(false); }}><section role="dialog" aria-modal="true" aria-labelledby="cv-project-spotlight-title" className="cv-project-spotlight__panel"><header><div><small>{projectId ? 'BUSCA NO PROJETO' : 'BUSCA NAS CONVERSAS'}</small><h2 id="cv-project-spotlight-title">{activeProject?.name || activeProject?.title || 'Conversas'}</h2></div><button type="button" onClick={() => setSpotlightOpen(false)} aria-label="Fechar busca"><Icon name="close" size={16}/></button></header><label className="cv-project-spotlight__input"><Icon name="search" size={17}/><input ref={spotlightInput} value={spotlightQuery} onChange={event => setSpotlightQuery(event.target.value)} placeholder={projectId ? 'Buscar arquivos, tarefas, atividades…' : 'Buscar conversas…'} aria-label={projectId ? 'Buscar nos itens do projeto' : 'Buscar conversas'}/><kbd>ESC</kbd></label><div className="cv-project-spotlight__results" aria-live="polite">{spotlightQuery.trim().length < 2 ? <p>Digite pelo menos 2 caracteres para iniciar a busca.</p> : spotlightLoading ? <p>Pesquisando…</p> : spotlightError ? <p role="alert">{spotlightError}</p> : spotlightResults.length ? spotlightResults.map(item => item.kind === 'resource' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); if (onOpenLibraryRef) onOpenLibraryRef(`resource:${item.id}`, activeProjectRef).catch(error => { setSpotlightError(error.message || 'Não foi possível abrir este recurso.'); setSpotlightOpen(true); }); else onOpenResource?.({...item, libraryRef:`resource:${item.id}`, project_ref:activeProjectRef}); }}><Icon name="file" size={15}/><span><b>{item.title}</b><small>{item.detail || 'Recurso do projeto'}</small></span><Icon name="chevron" size={13}/></button> : item.kind === 'conversation' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); onOpen(String(item.id), item.title); }}><Icon name="compose" size={15}/><span><b>{item.title}</b><small>{item.detail || 'Conversa do projeto'}</small></span><Icon name="chevron" size={13}/></button> : <a key={`${item.kind}-${item.id}`} href={item.kind === 'task' ? projectTasksUrl : projectActivityUrl}><Icon name={item.kind === 'task' ? 'check' : 'pulse'} size={15}/><span><b>{item.title}</b><small>{item.detail || 'Atividade do projeto'}</small></span><Icon name="chevron" size={13}/></a>) : <p>Nenhum item encontrado{projectId ? ' neste projeto' : ''}.</p>}</div>{projectId && <footer>Arquivos · documentos · tarefas · atividade</footer>}</section></div>, document.getElementById('cadu-conversations-v2-root') || document.body)}
  </>;
}
