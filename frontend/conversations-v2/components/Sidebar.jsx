import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {conversationDisplayTitle} from '../lib/conversationPresentation.mjs';

function contextLabel(item, projects, brands) {
  const project = projects.find(candidate => (candidate.ref || candidate.projectRef || candidate.id) === item.project_ref);
  if (project) return project.name;
  const brand = brands.find(candidate => (candidate.ref || candidate.brandRef || `studio:${candidate.id}`) === item.brand_ref);
  return brand ? brand.name : '';
}

function TimerIcon() {
  return <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><circle cx="8" cy="9" r="5.25" fill="none" stroke="currentColor" strokeWidth="1.3"/><path d="M8 9V6.2M6.2 2.1h3.6M11.8 4.2l1-1" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>;
}

export function Sidebar({conversations, projects = [], brands = [], activeProjectRef = '', navUrls = {}, activeId, onOpen, onOpenLibrary, onNewConversation, onOrganize, onConversationAction, open, onClose, loading, openingId}) {
  const sidebarRef = useRef(null);
  const previousFocus = useRef(null);
  const [query, setQuery] = useState('');
  const [showAllRecent, setShowAllRecent] = useState(false);
  const [actionMenuId, setActionMenuId] = useState('');
  const [rendered, setRendered] = useState(open);
  const ordered = useMemo(() => {
    const active = String(activeProjectRef || '');
    if (!active) return conversations;
    return [...conversations].sort((left, right) => {
      const leftActive = String(left.project_ref || '') === active;
      const rightActive = String(right.project_ref || '') === active;
      return Number(rightActive) - Number(leftActive);
    });
  }, [conversations, activeProjectRef]);
  const filtered = useMemo(() => ordered.filter(item =>
    `${item.title || ''} ${contextLabel(item, projects, brands)}`.toLocaleLowerCase('pt-BR').includes(query.trim().toLocaleLowerCase('pt-BR'))
  ), [ordered, projects, brands, query]);

  useEffect(() => setQuery(''), [activeProjectRef]);

  useEffect(() => {
    if (open) {
      setRendered(true);
      return undefined;
    }
    const timeout = window.setTimeout(() => setRendered(false), 190);
    return () => window.clearTimeout(timeout);
  }, [open]);

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

  if (!rendered) return null;
  const activeProject = projects.find(item => String(item.ref || item.projectRef || item.id) === String(activeProjectRef));
  const projectConversations = filtered.filter(item => String(item.project_ref || '') === String(activeProjectRef)).slice(0, 10);
  const otherConversations = filtered.filter(item => String(item.project_ref || '') !== String(activeProjectRef) && !['pinned', 'automation'].includes(item.section));
  const pinned = filtered.filter(item => item.section === 'pinned');
  const automations = filtered.filter(item => item.section === 'automation');
  const standard = filtered.filter(item => !['pinned', 'automation'].includes(item.section));
  const runAction = (event, item, action) => {
    event.stopPropagation();
    setActionMenuId('');
    onConversationAction?.(item, action);
  };
  const conversationList = (items, hideContext = false) => items.map(item => <div className="cv-conversation-row" key={item.id} draggable onDragStart={event => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('application/x-cadu-conversation', String(item.id)); }}>
    <button className="cv-conversation-card" type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={conversationDisplayTitle(item.title, 'Conversa sem título')}><span className="cv-conversation-card__copy"><b>{conversationDisplayTitle(item.title, 'Conversa sem título')}</b>{!hideContext && contextLabel(item, projects, brands) && <small>{contextLabel(item, projects, brands)}</small>}</span><span className={`cv-conversation-card__state ${item.running ? 'is-running' : ''}`} title={item.running ? 'Processo em andamento' : item.section === 'automation' && item.automation_enabled ? 'Automação agendada' : ''}>{item.running ? <i/> : item.section === 'automation' && item.automation_enabled ? <TimerIcon/> : null}</span></button>
    <div className={`cv-conversation-actions ${String(actionMenuId) === String(item.id) ? 'is-open' : ''}`}>
      <button type="button" className="cv-conversation-actions__trigger" aria-label={`Ações de ${item.title || 'conversa'}`} aria-expanded={String(actionMenuId) === String(item.id)} onClick={event => { event.stopPropagation(); setActionMenuId(current => String(current) === String(item.id) ? '' : String(item.id)); }}><span aria-hidden="true">•••</span></button>
      {String(actionMenuId) === String(item.id) && <div className="cv-conversation-actions__menu" role="menu">
        <button type="button" role="menuitem" onClick={event => runAction(event, item, 'toggle-pin')}>{item.section === 'pinned' ? 'Desafixar' : 'Fixar conversa'}</button>
        {item.section === 'automation' && item.automation_enabled && <button type="button" role="menuitem" onClick={event => runAction(event, item, 'stop-automation')}>Encerrar automação</button>}
        <button type="button" role="menuitem" className="is-danger" onClick={event => runAction(event, item, 'archive')}>Arquivar</button>
      </div>}
    </div>
  </div>);
  const dropSection = (section, label, items) => items.length ? <section className={`cv-conversation-section is-${section}`} onDragOver={event => { if (event.dataTransfer.types.includes('application/x-cadu-conversation')) event.preventDefault(); }} onDrop={event => { event.preventDefault(); const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, section); }}><header><span>{label}</span><b>{items.length || ''}</b></header>{conversationList(items)}</section> : null;
  return <>
    <button type="button" onClick={onClose} aria-label="Fechar chats recentes" tabIndex={open ? 0 : -1} className={`cv-recent-backdrop ${open ? 'is-visible' : 'is-closing'}`}/>
    <aside ref={sidebarRef} id="cv-recent-sidebar" role={window.matchMedia('(max-width: 767px)').matches ? 'dialog' : undefined} aria-modal={window.matchMedia('(max-width: 767px)').matches ? 'true' : undefined} className={`cv-recent-sidebar ${open ? 'is-open' : 'is-closing'}`} aria-hidden={!open} inert={!open ? '' : undefined} aria-label="Chats recentes">
      <div className="cv-mobile-navigation">
        <header><div><small>{activeProject ? 'Projeto atual' : 'Cadu Chat'}</small><strong>{activeProject?.name || activeProject?.title || 'Conversas'}</strong></div><button type="button" onClick={onClose} aria-label="Fechar navegação"><Icon name="close" size={18}/></button></header>
        <div className="cv-mobile-navigation__scroll">
          <button type="button" className="cv-mobile-navigation__primary" onClick={onNewConversation}>Nova conversa</button>
          <label className="cv-mobile-navigation__search"><Icon name="search" size={16}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversa"/></label>
          {!!pinned.length && <section><h2>Fixadas</h2>{conversationList(pinned.slice(0, 5))}</section>}
          {!!automations.length && <section><h2>Automações</h2>{conversationList(automations.slice(0, 5))}</section>}
          <section><h2>Recentes</h2>{conversationList(standard.slice(0, query ? 30 : 5))}{standard.length > 5 && !query && <button type="button" className="cv-mobile-navigation__more" onClick={event => { event.currentTarget.closest('section')?.classList.add('is-expanded'); }}>Ver todas</button>}{standard.length > 5 && !query && <div className="cv-mobile-navigation__extra">{conversationList(standard.slice(5))}</div>}</section>
          <nav aria-label="Outras áreas"><button type="button" onClick={onOpenLibrary}><Icon name="file" size={17}/>Biblioteca</button>{navUrls.docs && <a href={navUrls.docs}>Arquivos</a>}{navUrls.profile && <a href={navUrls.profile}>Configurações</a>}</nav>
        </div>
      </div>
      <div className="cv-desktop-history">
      <header className="cv-recent-sidebar__header">
        <div><span>{activeProject ? 'Projeto ativo' : 'Cadu Chat'}</span><strong>{activeProject?.name || activeProject?.title || 'Recentes'}</strong></div>
        <div><button type="button" onClick={onClose} aria-label="Recolher chats recentes"><Icon name="chevron" size={16}/></button></div>
      </header>
      {conversations.length > 6 && <label className="cv-recent-search"><Icon name="search" size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversa"/></label>}
      <div className="cv-recent-list">
        <button type="button" className="cv-recent-library-button" onClick={onOpenLibrary}><Icon name="file" size={16}/>Biblioteca</button>
        {dropSection('pinned', 'Conversas fixadas', pinned)}
        {dropSection('automation', 'Automações', automations)}
        {activeProject && <section className="cv-recent-project-section" onDragOver={event => event.preventDefault()} onDrop={event => { const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, 'recent'); }}><header><span>Conversas</span><b>Últimas 10</b></header>{conversationList(projectConversations.filter(item => !['pinned', 'automation'].includes(item.section)), true)}{!loading && !projectConversations.some(item => !['pinned', 'automation'].includes(item.section)) && <p>{query.trim() ? 'Nenhuma conversa deste projeto corresponde à busca.' : 'Ainda não há conversas deste projeto.'}</p>}</section>}
            {!activeProject && <section className="cv-recent-project-section" onDragOver={event => event.preventDefault()} onDrop={event => { const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, 'recent'); }}><header><span>Conversas recentes</span><b>{standard.length || ''}</b></header>{conversationList(standard.slice(0, showAllRecent || query ? undefined : 5))}{standard.length > 5 && !query && <button type="button" className="cv-recent-show-all" onClick={() => setShowAllRecent(value => !value)}>{showAllRecent ? 'Mostrar menos' : 'Ver todas'}</button>}{loading && !conversations.length && <div className="cv-recent-loading" aria-label="Carregando conversas"><i/><i/><i/></div>}{!loading && !filtered.length && <p>{query.trim() ? 'Nenhuma conversa corresponde à busca.' : 'Suas conversas aparecerão aqui.'}</p>}</section>}
        {activeProject && <details className="cv-recent-all-section"><summary>Outras conversas <b>{otherConversations.length}</b></summary><div>{conversationList(otherConversations.slice(0, 8))}</div></details>}
      </div>
      </div>
    </aside>
  </>;
}
