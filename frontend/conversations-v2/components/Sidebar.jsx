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
import {groupWorkspaceProjects, isArchivedEntity, nextBrandSelection, projectsForBrandSelection, workspaceBrandByRef} from '../../cadu-design-system/workspaceEntities.mjs';

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

function ConversationActionsMenu({item, projects, sections, panel, setPanel, renameDraft, setRenameDraft, sectionDraft, setSectionDraft, notice, setNotice, busy, shareUrl, setShareUrl, run, createSection, copyText, onOpen, onOpenLibrary, close, style}) {
  const projectRef = item.project_ref || '';
  const submitRename = event => { event.preventDefault(); const title = renameDraft.trim(); if (title) run(item, 'rename', title); };
  const createAndMove = async event => {
    event.preventDefault();
    if (!sectionDraft.trim()) return;
    try {
      const section = await createSection?.(sectionDraft.trim());
      if (section) await run(item, 'set-section', {section: 'custom', custom_section_id: section.id, custom_section_name: section.name});
    } catch (error) { setNotice(error.message || 'Não foi possível criar a seção.'); }
  };
  const createShare = async () => { const share = await run(item, 'share', null, false); if (share?.url) { setShareUrl(share.url); setPanel('share'); } };
  const shareCopy = async () => {
    try { await copyText(shareUrl); }
    catch (_) { /* copyText already reports clipboard errors in the menu */ }
  };
  const copyTranscript = async () => {
    const result = await run(item, 'copy-transcript', null, false);
    if (result?.text) await copyText(result.text);
  };
  const copyConversationLink = () => copyText(`${window.location.origin}${window.location.pathname}?conversation_id=${encodeURIComponent(item.id)}`);
  return <div className="cv-conversation-actions__menu" role="menu" style={style} onClick={event => event.stopPropagation()}>
    {panel === 'rename' ? <form className="cv-action-form" onSubmit={submitRename}>
      <label htmlFor={`cv-rename-${item.id}`}>Renomear conversa</label>
      <input id={`cv-rename-${item.id}`} autoFocus maxLength={150} value={renameDraft} onChange={event => setRenameDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Escape') setPanel(''); }}/>
      <div><button type="button" onClick={() => setPanel('')}>Cancelar</button><button type="submit" disabled={!renameDraft.trim() || busy}>Salvar</button></div>
    </form> : panel === 'project' ? <div className="cv-action-submenu">
      <button type="button" className="cv-action-back" onClick={() => setPanel('')}>‹ <span>Mover para projeto</span></button>
      <button type="button" className={!projectRef ? 'is-selected' : ''} onClick={() => run(item, 'move-project', null)}>Sem projeto</button>
      {projects.map(project => { const ref = String(project.ref || project.projectRef || project.id); return <button type="button" className={projectRef === ref ? 'is-selected' : ''} key={ref} onClick={() => run(item, 'move-project', ref)}>{project.name || project.title || 'Projeto'}</button>; })}
    </div> : panel === 'section' ? <div className="cv-action-submenu">
      <button type="button" className="cv-action-back" onClick={() => setPanel('')}>‹ <span>Seção</span></button>
      {[['recent', 'Recentes'], ['pinned', 'Fixadas']].map(([section, label]) => <button type="button" className={item.section === section ? 'is-selected' : ''} key={section} onClick={() => run(item, 'set-section', {section})}>{label}</button>)}
      {sections.map(section => <button type="button" className={item.custom_section_id === section.id ? 'is-selected' : ''} key={section.id} onClick={() => run(item, 'set-section', {section: 'custom', custom_section_id: section.id, custom_section_name: section.name})}>{section.name}</button>)}
      <form className="cv-action-create-section" onSubmit={createAndMove}><input aria-label="Nome da nova seção" maxLength={64} placeholder="Criar seção…" value={sectionDraft} onChange={event => setSectionDraft(event.target.value)}/><button type="submit" disabled={!sectionDraft.trim() || busy} aria-label="Adicionar seção"><Icon name="plus" size={14}/></button></form>
    </div> : panel === 'copy' ? <div className="cv-action-submenu">
      <button type="button" className="cv-action-back" onClick={() => setPanel('')}>‹ <span>Copiar</span></button>
      <button type="button" onClick={copyTranscript}>Copiar conversa como Markdown</button><button type="button" onClick={copyConversationLink}>Copiar link da conversa</button>
    </div> : panel === 'open' ? <div className="cv-action-submenu">
      <button type="button" className="cv-action-back" onClick={() => setPanel('')}>‹ <span>Abrir em</span></button>
      <button type="button" onClick={() => { close(); onOpen(String(item.id), item.title); }}>Esta janela</button>
      <button type="button" onClick={() => window.open(`${window.location.origin}${window.location.pathname}?conversation_id=${encodeURIComponent(item.id)}`, '_blank', 'noopener,noreferrer')}>Nova janela</button>
      {projectRef && <button type="button" onClick={() => { close(); onOpenLibrary?.(true, projectRef); }}>Arquivos do projeto</button>}
    </div> : panel === 'share' ? <div className="cv-action-share">
      <label htmlFor={`cv-share-${item.id}`}>Link compartilhável · expira em 30 dias</label><input id={`cv-share-${item.id}`} readOnly value={shareUrl}/>
      <button type="button" onClick={shareCopy}><Icon name="copy" size={14}/>Copiar link</button>
      <button type="button" onClick={async () => { const result = await run(item, 'revoke-share', null, false); if (result?.revoked) { setShareUrl(''); setPanel(''); } }}>Revogar link</button>
    </div> : <>
      <button type="button" onClick={() => { setRenameDraft(item.title || ''); setPanel('rename'); }}><Icon name="compose" size={15}/>Renomear</button>
      <button type="button" onClick={() => run(item, item.is_unread ? 'mark-read' : 'mark-unread')}><Icon name={item.is_unread ? 'check' : 'alert'} size={15}/>{item.is_unread ? 'Marcar como lida' : 'Marcar como não lida'}</button>
      <button type="button" onClick={() => setPanel('project')}><Icon name="folder" size={15}/>Projeto <span className="cv-action-chevron">›</span></button>
      <button type="button" onClick={() => setPanel('section')}><Icon name="list" size={15}/>Seção <span className="cv-action-chevron">›</span></button>
      <button type="button" onClick={createShare}><Icon name="share" size={15}/>Compartilhar</button>
      <button type="button" onClick={() => setPanel('copy')}><Icon name="copy" size={15}/>Copiar <span className="cv-action-chevron">›</span></button>
      <button type="button" onClick={() => setPanel('open')}><Icon name="external" size={15}/>Abrir em <span className="cv-action-chevron">›</span></button>
      <button type="button" title="Clona o texto e o contexto; não copia anexos nem artefatos" onClick={() => run(item, 'fork')}><Icon name="branch" size={15}/>Criar ramificação</button>
      {item.section === 'automation' && item.automation_enabled && <button type="button" onClick={() => run(item, 'stop-automation')}><Icon name="clock" size={15}/>Encerrar automação</button>}
      <div className="cv-action-separator"/><button type="button" className="is-danger" onClick={() => run(item, 'archive')}><Icon name="archive" size={15}/>Arquivar</button>
    </>}
    {notice && <div className="cv-action-notice" role="status">{notice}</div>}
  </div>;
}

export function Sidebar({conversations, conversationSections = [], projects = [], brands = [], activeProjectRef = '', activeBrandRef = '', artifactOpen = false, pluginsPageOpen = false, navUrls = {}, historyEndpoint = '', solutions = [], logo, user = {}, usagePercent = 0, activeId, currentTitle = '', onOpen, onOpenLibrary, onOpenResource, onOpenLibraryRef, onOpenBrandArtifact, onOpenPlugins, onClosePlugins, onNewConversation, onProjectChange, onCreateProject, onConversationAction, onCreateConversationSection, open, onOpenSidebar, onClose, loading, historyError = '', onRetryHistory, historyHasMore = false, onLoadMoreHistory, openingId}) {
  const sidebarRef = useRef(null);
  const previousFocus = useRef(null);
  const [showAllRecent, setShowAllRecent] = useState(false);
  const [recentCollapsed, setRecentCollapsed] = useState(false);
  const [showMoreProjects, setShowMoreProjects] = useState(false);
  const [selectedBrandRef, setSelectedBrandRef] = useState(activeBrandRef ? String(activeBrandRef) : '');
  const [showAllProjectConversations, setShowAllProjectConversations] = useState({});
  const [expandedProjects, setExpandedProjects] = useState(() => new Set(activeProjectRef ? [String(activeProjectRef)] : []));
  const [projectMenuId, setProjectMenuId] = useState('');
  const [actionMenuId, setActionMenuId] = useState('');
  const [actionMenuPosition, setActionMenuPosition] = useState(null);
  const [actionPanel, setActionPanel] = useState('');
  const [renameDraft, setRenameDraft] = useState('');
  const [sectionDraft, setSectionDraft] = useState('');
  const [actionNotice, setActionNotice] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const actionBusyRef = useRef(false);
  const [shareUrl, setShareUrl] = useState('');
  const notifications = useWorkspaceNotifications();
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [spotlightQuery, setSpotlightQuery] = useState('');
  const [spotlightResults, setSpotlightResults] = useState([]);
  const [spotlightLoading, setSpotlightLoading] = useState(false);
  const [spotlightError, setSpotlightError] = useState('');
  const spotlightInput = useRef(null);
  const searchSequence = useRef(0);
  const searchRequest = useRef(null);
  const desktopMode = window.matchMedia('(min-width: 768px)').matches;
  const desktopClosed = desktopMode && !open;
  const ordered = conversations;
  const filtered = ordered;
  const activeProject = projects.find(item => String(item.ref || item.projectRef || item.id) === String(activeProjectRef));
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
    setRecentCollapsed(Boolean(activeProjectRef || selectedBrandRef));
  }, [activeProjectRef, selectedBrandRef]);

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
      if (!event.target.closest('.cv-conversation-actions') && !event.target.closest('.cv-conversation-actions__menu')) {
        setActionMenuId(''); setActionPanel('');
      }
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
    searchRequest.current?.abort();
    searchRequest.current = null;
    if (!spotlightOpen || query.length < 2) {
      setSpotlightResults([]); setSpotlightLoading(false); setSpotlightError('');
      return () => { searchSequence.current += 1; };
    }
    const controller = new AbortController();
    searchRequest.current = controller;
    const timer = window.setTimeout(async () => {
      setSpotlightLoading(true); setSpotlightError('');
      try {
        if (!projectId) {
          const url = new URL(historyEndpoint || '/familia/api/conversations', window.location.origin);
          url.searchParams.set('q', query);
          url.searchParams.set('page_size', '40');
          const data = await request(url.toString(), {signal: controller.signal});
          const results = (data.conversations || []).map(item => ({
            id: item.id, kind: 'conversation', title: item.title || 'Conversa',
            detail: contextLabel(item, projects, brands),
          }));
          if (sequence === searchSequence.current) setSpotlightResults(results);
          return;
        }
        const [data, history] = await Promise.all([
          request(`/workspace/api/projetos/${encodeURIComponent(projectId)}/buscar?q=${encodeURIComponent(query)}`, {signal: controller.signal}),
          (async () => {
            const url = new URL(historyEndpoint || '/familia/api/conversations', window.location.origin);
            url.searchParams.set('q', query);
            url.searchParams.set('page_size', '40');
            return request(url.toString(), {signal: controller.signal});
          })(),
        ]);
        const conversationResults = (history.conversations || []).filter(item => String(item.project_ref || '') === String(activeProjectRef)).slice(0, 10).map(item => ({id: item.id, kind: 'conversation', title: item.title || 'Conversa'}));
        if (sequence === searchSequence.current) setSpotlightResults([...(data.results || []), ...conversationResults].slice(0, 40));
      } catch (error) {
        if (error.name !== 'AbortError' && sequence === searchSequence.current) { setSpotlightResults([]); setSpotlightError(error.message || 'Não foi possível pesquisar o projeto.'); }
      } finally {
        if (sequence === searchSequence.current) {
          searchRequest.current = null;
          setSpotlightLoading(false);
        }
      }
    }, 160);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
      if (searchRequest.current === controller) searchRequest.current = null;
      searchSequence.current += 1;
    };
  }, [spotlightOpen, spotlightQuery, projectId, conversations, projects, brands, activeProjectRef, historyEndpoint]);

  useEffect(() => {
    if (!activeProjectRef) return;
    const ref = String(activeProjectRef);
    setExpandedProjects(current => current.has(ref) ? current : new Set([...current, ref]));
  }, [activeProjectRef]);

  const pinnedConversations = filtered.filter(item => item.section === 'pinned');
  const customSectionConversations = section => filtered.filter(item => String(item.custom_section_id || '') === String(section.id));
  const automations = filtered.filter(item => item.section === 'automation' && item.automation_enabled);
  const standard = filtered.filter(item => !item.project_ref && !item.brand_ref && (!item.section || item.section === 'recent'));
  const activeConversation = conversations.find(item => String(item.id) === String(activeId));
  const mobileDestinations = workspaceMobileDestinationItems(navUrls);
  const mobileSolutions = workspaceMobileSolutionItems(navUrls);
  const projectItems = [...projects].sort((left, right) => String(left.name || left.title || '').localeCompare(String(right.name || right.title || ''), 'pt-BR', {sensitivity: 'base'}));
  const actionItem = conversations.find(item => String(item.id) === String(actionMenuId));
  const workspaceGroups = groupWorkspaceProjects(brands.filter(brand => !isArchivedEntity(brand) && !brand.archived && !brand.isArchived), projectItems);
  const brandItems = workspaceGroups.groups.filter(brand => brand.projects.length > 0);
  const ungroupedProjects = workspaceGroups.ungrouped;
  const selectedBrand = workspaceBrandByRef(brandItems, selectedBrandRef);
  const displayedProjects = projectsForBrandSelection(brandItems, ungroupedProjects, selectedBrandRef);
  const activeProjectBrand = activeProjectRef
    ? brandItems.find(brand => brand.projects.some(project => String(project.ref || project.projectRef || project.id) === String(activeProjectRef)))
    : null;
  const activeProjectBrandRef = activeProjectBrand
    ? String(activeProjectBrand.ref || activeProjectBrand.brandRef || (activeProjectBrand.id ? `studio:${activeProjectBrand.id}` : ''))
    : '';
  const activeBrand = workspaceBrandByRef(brandItems, activeBrandRef);
  const restoredBrandRef = activeBrand
    ? String(activeBrand.ref || activeBrand.brandRef || (activeBrand.id ? `studio:${activeBrand.id}` : activeBrand.name))
    : activeProjectBrandRef;
  useEffect(() => {
    setSelectedBrandRef(restoredBrandRef);
  }, [activeBrandRef, activeProjectRef, projects, brands]);
  if (!open && !desktopMode) return null;
  const toggleBrand = ref => {
    const nextRef = nextBrandSelection(selectedBrandRef, ref);
    const selectedBrand = workspaceBrandByRef(brandItems, nextRef);
    const currentProject = selectedBrand?.projects.find(project => String(project.ref || project.projectRef || project.id) === String(activeProjectRef));
    const nextProject = currentProject || selectedBrand?.projects[0];
    setSelectedBrandRef(nextRef);
    setRecentCollapsed(Boolean(nextRef));
    setShowMoreProjects(false);
    if (nextProject) {
      const projectRef = String(nextProject.ref || nextProject.projectRef || nextProject.id);
      setExpandedProjects(new Set([projectRef]));
    } else setExpandedProjects(new Set());
  };
  const selectUnbrandedProjects = () => {
    const currentProject = ungroupedProjects.find(project => String(project.ref || project.projectRef || project.id) === String(activeProjectRef));
    const nextProject = currentProject || ungroupedProjects[0];
    setSelectedBrandRef('');
    setRecentCollapsed(true);
    setShowMoreProjects(false);
    if (nextProject) {
      const projectRef = String(nextProject.ref || nextProject.projectRef || nextProject.id);
      setExpandedProjects(new Set([projectRef]));
    } else setExpandedProjects(new Set());
  };
  const renderProjectItem = (project, extraClass = '') => {
    const ref = String(project.ref || project.projectRef || project.id);
    const isOpen = expandedProjects.has(ref);
    const items = filtered.filter(item => String(item.project_ref || '') === ref && item.section === 'recent');
    const showAll = Boolean(showAllProjectConversations[ref]);
    const projectName = project.name || project.title || 'Projeto';
    const projectUrl = `/projetos/${encodeURIComponent(String(project.id || ref).replace(/^ci:/,''))}`;
    const selected = ref === String(activeProjectRef);
    return <section key={ref} className={`cv-project-tree__item${extraClass ? ` ${extraClass}` : ''}${isOpen ? ' is-open' : ''}${selected ? ' is-active' : ''}`}>
      <div className="cv-project-tree__heading">
        <button type="button" className="cv-project-tree__trigger" aria-expanded={isOpen} aria-current={selected ? 'location' : undefined} onClick={() => { if (selected) setExpandedProjects(current => current.has(ref) ? new Set() : new Set([ref])); else setExpandedProjects(new Set([ref])); setRecentCollapsed(true); if (!selected) onProjectChange?.(ref); }}>
          <SidebarTitle className="cv-project-tree__name">{projectName}</SidebarTitle>
        </button>
        <div className={`cv-project-menu${projectMenuId === ref ? ' is-open' : ''}`}>
          <button type="button" className="cv-project-menu__new-chat" aria-label={`Nova conversa em ${projectName}`} title={`Nova conversa em ${projectName}`} onClick={event => { event.stopPropagation(); startProjectConversation(ref); }}><Icon name="newChat" size={15}/></button>
          <button type="button" className="cv-project-menu__trigger" aria-label={`Mais ações para ${projectName}`} aria-expanded={projectMenuId === ref} onClick={event => { event.stopPropagation(); setProjectMenuId(current => current === ref ? '' : ref); }}><span aria-hidden="true">…</span></button>
          {projectMenuId === ref && <div className="cv-project-menu__popover"><a href={projectUrl}><NavIcon name="folderOpen"/><span>Abrir projeto</span></a><button type="button" onClick={() => { setProjectMenuId(''); startProjectConversation(ref); }}><Icon name="newChat" size={16}/><span>Nova conversa</span></button><button type="button" onClick={() => { setProjectMenuId(''); openIndex(ref); }}><NavIcon name="library"/><span>Abrir arquivos</span></button></div>}
        </div>
      </div>
      {isOpen && <div className="cv-project-tree__children">{items.slice(0, showAll ? undefined : 5).map(item => conversationList([item], true))}{items.length > 5 && <button type="button" className="cv-project-tree__more" onClick={() => setShowAllProjectConversations(current => ({...current, [ref]: !current[ref]}))}>{showAll ? 'Mostrar menos' : 'Mostrar mais'}</button>}{!items.length && <small>Sem chats</small>}</div>}
    </section>;
  };
  const openIndex = ref => { if (ref || activeProjectRef) onOpenLibrary?.(true, ref || activeProjectRef); else setSpotlightError('Selecione um projeto para abrir os arquivos.'); };
  const startProjectConversation = async ref => {
    if (String(ref) !== String(activeProjectRef)) await onProjectChange?.(ref);
    onNewConversation?.();
  };
  const openActionMenu = (event, item) => {
    event.stopPropagation();
    if (String(actionMenuId) === String(item.id)) { setActionMenuId(''); setActionPanel(''); return; }
    const rect = event.currentTarget.getBoundingClientRect();
    const width = 224;
    const maxHeight = Math.min(440, window.innerHeight - 24);
    const below = rect.bottom + 4;
    const spaceBelow = window.innerHeight - below - 8;
    const openAbove = spaceBelow < 240 && rect.top > 240;
    const top = openAbove
      ? Math.max(8, Math.min(rect.top - maxHeight - 4, window.innerHeight - maxHeight - 8))
      : below;
    const availableHeight = openAbove ? window.innerHeight - top - 8 : spaceBelow;
    const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
    setActionMenuPosition({top, left, maxHeight: Math.min(maxHeight, availableHeight)});
    setActionMenuId(String(item.id));
    setActionPanel(''); setActionNotice(''); setShareUrl(''); setSectionDraft('');
  };
  const performConversationAction = async (item, action, value, close = true) => {
    if (actionBusyRef.current) return null;
    actionBusyRef.current = true;
    setActionBusy(true); setActionNotice('');
    try {
      const result = await onConversationAction?.(item, action, value);
      if (close) { setActionMenuId(''); setActionPanel(''); }
      return result;
    } catch (error) {
      setActionNotice(error.message || 'Não foi possível concluir esta ação.');
      return null;
    } finally { actionBusyRef.current = false; setActionBusy(false); }
  };
  const copyText = async value => {
    try { await navigator.clipboard.writeText(value); setActionNotice('Copiado para a área de transferência.'); }
    catch (_) { setActionNotice('Não foi possível copiar automaticamente. Selecione e copie o texto.'); }
  };
  const runAction = (event, item, action) => { event.stopPropagation(); performConversationAction(item, action); };
  const conversationList = (items, hideContext = false) => items.map(item => { const context = contextLabel(item, projects, brands); const menuOpen = String(actionMenuId) === String(item.id); return <div className="cv-conversation-row" key={item.id}>
    <button className="cv-conversation-card" type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={conversationDisplayTitle(item.title, 'Chat sem título')}><span className="cv-conversation-card__copy"><b><SidebarTitle>{conversationDisplayTitle(item.title, 'Chat sem título')}</SidebarTitle></b>{!hideContext && <small>{context || 'Sessão livre'}</small>}</span>{item.awaiting_response && <span className="cv-conversation-card__state is-awaiting-response" title="Precisa da sua resposta" aria-label="Precisa da sua resposta"><Icon name="alert" size={14}/></span>}</button>
    <div className={`cv-conversation-actions ${String(actionMenuId) === String(item.id) ? 'is-open' : ''}`}>
      <button type="button" className="cv-conversation-actions__archive" aria-label={`Arquivar ${item.title || 'conversa'}`} title="Arquivar conversa" onClick={event => runAction(event, item, 'archive')}><Icon name="archive" size={14}/></button>
      <button type="button" className="cv-conversation-actions__trigger" aria-label={`Mais ações para ${item.title || 'conversa'}`} aria-expanded={menuOpen} onClick={event => openActionMenu(event, item)}><Icon name="more" size={15}/></button>
    </div>
  </div>; });
  return <>
    {open && <button type="button" onClick={onClose} aria-label="Fechar chats recentes" className="cv-recent-backdrop is-visible"/>}
    <aside ref={sidebarRef} id="cv-recent-sidebar" role={!desktopMode ? 'dialog' : undefined} aria-modal={!desktopMode ? 'true' : undefined} className={`cv-recent-sidebar ${desktopClosed ? 'is-closed' : 'is-open'}`} aria-label="Chats recentes">
      {desktopClosed ? <div className="cv-sidebar-mini-rail">
        <CaduSolutionSwitcher logo={logo} solutions={solutions} activeId="workspace"/><button type="button" className="cv-sidebar-mini-rail__expand" onClick={onOpenSidebar} aria-label="Expandir sidebar" title="Expandir sidebar"><NavIcon name="expand"/></button>
      </div> : <>
      <div className="cv-mobile-navigation">
        <header><div><strong>Workspace</strong><small>{conversationDisplayTitle(currentTitle || activeConversation?.title, 'Novo chat')}</small></div><button type="button" onClick={onClose} aria-label="Fechar navegação"><NavIcon name="close"/></button></header>
        <div className="cv-mobile-navigation__scroll">
          <button type="button" className="cv-mobile-navigation__primary" onClick={onNewConversation}>Novo chat</button>
          {activeProject && projectDetailsUrl && <a className="cv-mobile-navigation__project-link" href={projectDetailsUrl} onClick={onClose}><NavIcon name="folder"/><span>{activeProject.name || activeProject.title}</span></a>}
          <div className="cv-sidebar-project-tools"><button type="button" title="Buscar no projeto" aria-label="Buscar no projeto" onClick={() => { setSpotlightQuery(''); setSpotlightOpen(true); }}><NavIcon name="search"/></button></div>
          {!selectedBrandRef && !!automations.length && <section><h2>Automações</h2>{conversationList(automations.slice(0, 5))}</section>}
          {!selectedBrandRef && !!pinnedConversations.length && <section><h2>Fixadas</h2>{conversationList(pinnedConversations)}</section>}
          {!selectedBrandRef && conversationSections.map(section => { const items = customSectionConversations(section); return items.length ? <section key={section.id}><h2>{section.name}</h2>{conversationList(items)}</section> : null; })}
          {!selectedBrandRef && <section><h2>Chats recentes</h2>{conversationList(standard.slice(0, 5))}{standard.length > 5 && <button type="button" className="cv-mobile-navigation__more" onClick={event => { event.currentTarget.closest('section')?.classList.add('is-expanded'); }}>Ver todos</button>}{standard.length > 5 && <div className="cv-mobile-navigation__extra">{conversationList(standard.slice(5))}</div>}</section>}
          {!!brandItems.length && <section className="cv-mobile-entity-tree cv-mobile-entity-tree--brands"><h2>Marcas</h2><div className="cv-brand-tree__list">{brandItems.map(brand => { const ref = String(brand.ref || brand.brandRef || (brand.id ? `studio:${brand.id}` : brand.name)); const selected = selectedBrandRef === ref; return <button type="button" className={`cv-brand-tree__choice${selected ? ' is-selected' : ''}`} key={`mobile-${ref}`} aria-pressed={selected} onClick={() => toggleBrand(ref)}>{brand.name || brand.title || 'Marca'}</button>; })}</div></section>}
          <section className="cv-mobile-entity-tree cv-project-selection"><div className="cv-mobile-entity-tree__heading"><h2>Projetos</h2><button type="button" onClick={onCreateProject}>Novo</button></div>{!!ungroupedProjects.length && !selectedBrandRef && <button type="button" className="cv-brand-tree__choice cv-project-selection__unbranded is-selected" aria-pressed="true" onClick={selectUnbrandedProjects}>Sem marca</button>}{displayedProjects.map(project => renderProjectItem(project, selectedBrand ? 'cv-brand-tree__project' : ''))}{!displayedProjects.length && <p>{selectedBrandRef ? 'Esta marca ainda não tem projetos.' : 'Nenhum projeto sem marca.'}</p>}</section>
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
          <div className="cv-sidebar-primary-nav__scheduled"><button className="cv-nav-action" type="button" aria-expanded={automations.length > 0 ? showAllRecent : undefined} onClick={() => automations.length ? setShowAllRecent(value => !value) : null}><Icon name="clock" size={17}/><span>Agendado</span>{automations.length > 0 && <b>{automations.length}</b>}</button>{automations.length > 0 && showAllRecent && <div className="cv-sidebar-primary-nav__scheduled-items">{conversationList(automations)}</div>}</div>
          <button className={`cv-nav-action${pluginsPageOpen ? ' is-active' : ''}`} type="button" aria-current={pluginsPageOpen ? 'page' : undefined} onClick={pluginsPageOpen ? onClosePlugins : onOpenPlugins}><Icon name="plugin" size={17}/><span>Plugins</span></button>
          <button className="cv-nav-action" type="button" onClick={() => openIndex(activeProjectRef)}><Icon name="library" size={17}/><span>Arquivos</span></button>
        </nav>
        {!!brandItems.length && <section className="cv-nav-group cv-project-tree cv-brand-tree" aria-label="Marcas"><header><span>Marcas</span></header><div className="cv-brand-tree__list">{brandItems.map(brand => {
          const ref = String(brand.ref || brand.brandRef || (brand.id ? `studio:${brand.id}` : brand.name));
          const selected = selectedBrandRef === ref;
          const brandName = brand.name || brand.title || 'Marca';
          return <button key={ref} type="button" className={`cv-brand-tree__choice${selected ? ' is-selected' : ''}`} aria-pressed={selected} onClick={() => toggleBrand(ref)} title={brandName}>{brandName}</button>;
        })}</div></section>}
        <section className="cv-nav-group cv-project-tree cv-unbranded-projects cv-project-selection" aria-label="Projetos"><header><span>Projetos</span><button type="button" className="cv-project-selection__create" onClick={onCreateProject}>Novo</button></header>{!!ungroupedProjects.length && !selectedBrandRef && <button type="button" className="cv-brand-tree__choice cv-project-selection__unbranded is-selected" aria-pressed="true" onClick={selectUnbrandedProjects}>Sem marca</button>}{displayedProjects.slice(0, showMoreProjects ? undefined : 6).map(project => renderProjectItem(project, selectedBrand ? 'cv-brand-tree__project' : ''))}{displayedProjects.length > 6 && <button type="button" className="cv-project-tree__more" onClick={() => setShowMoreProjects(value => !value)}>{showMoreProjects ? 'Mostrar menos' : 'Mostrar mais'}</button>}{!displayedProjects.length && <small className="cv-unbranded-projects__empty">{selectedBrandRef ? 'Esta marca ainda não tem projetos.' : 'Nenhum projeto sem marca.'}</small>}</section>
        {!selectedBrandRef && !!pinnedConversations.length && <section className="cv-nav-group cv-section-conversations"><header><span>Fixadas</span></header>{conversationList(pinnedConversations, true)}</section>}
        {!selectedBrandRef && conversationSections.map(section => { const items = customSectionConversations(section); return items.length ? <section className="cv-nav-group cv-section-conversations" key={section.id}><header><SidebarTitle>{section.name}</SidebarTitle></header>{conversationList(items, true)}</section> : null; })}
        {!selectedBrandRef && <section className={`cv-nav-group cv-personal-recent${recentCollapsed ? ' is-collapsed' : ''}`}><header><button type="button" className="cv-personal-recent__toggle" aria-expanded={!recentCollapsed} onClick={() => setRecentCollapsed(value => !value)}><span>Recentes</span><NavIcon name="chevron"/></button></header>{!recentCollapsed && <>{conversationList(standard.slice(0, showAllRecent ? undefined : 5), true)}{(standard.length > 5 || historyHasMore) && <button type="button" className="cv-project-tree__more" disabled={loading} onClick={() => { if (!showAllRecent) { setShowAllRecent(true); if (standard.length <= 5 || historyHasMore) onLoadMoreHistory?.(); } else if (historyHasMore) onLoadMoreHistory?.(); else setShowAllRecent(false); }}>{loading && conversations.length ? 'Carregando…' : !showAllRecent && standard.length > 5 ? 'Mostrar mais' : historyHasMore ? 'Carregar mais conversas' : 'Mostrar menos'}</button>}{loading && !conversations.length && <div className="cv-recent-loading" aria-label="Carregando conversas"><i/><i/><i/></div>}{!loading && historyError && <div className="cv-history-error" role="alert"><p>{historyError}</p><button type="button" onClick={onRetryHistory}>Tentar novamente</button></div>}{!loading && !historyError && !standard.length && <p>Nenhuma conversa recente.</p>}</>}</section>}
      </div>
      <footer className="cv-chat-sidebar-footer">{navUrls.profile ? <a href={navUrls.profile} aria-label={`Perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></a> : <button type="button" aria-label={`Abrir perfil de ${user.name || 'usuário'}`}><VisualIdentity src={user.avatar} initials={user.name} label={user.name} imageAlt={`Foto de ${user.name || 'usuário'}`}/><span>{user.name || 'Perfil'}</span></button>}<UsageMiniChart percent={usagePercent}/></footer>
      </div>
      </>}
    </aside>
    {actionMenuId && actionItem && actionMenuPosition && createPortal(<ConversationActionsMenu item={actionItem} projects={projectItems} sections={conversationSections} panel={actionPanel} setPanel={setActionPanel} renameDraft={renameDraft} setRenameDraft={setRenameDraft} sectionDraft={sectionDraft} setSectionDraft={setSectionDraft} notice={actionNotice} setNotice={setActionNotice} busy={actionBusy} shareUrl={shareUrl} setShareUrl={setShareUrl} run={performConversationAction} createSection={onCreateConversationSection} copyText={copyText} onOpen={onOpen} onOpenLibrary={onOpenLibrary} close={() => {setActionMenuId(''); setActionPanel('');}} style={actionMenuPosition}/>, document.getElementById('cadu-conversations-v2-root') || document.body)}
    {spotlightOpen && createPortal(<div className="cv-project-spotlight" onMouseDown={event => { if (event.target === event.currentTarget) setSpotlightOpen(false); }}><section role="dialog" aria-modal="true" aria-labelledby="cv-project-spotlight-title" className="cv-project-spotlight__panel"><header><div><small>{projectId ? 'BUSCA NO PROJETO' : 'BUSCA NAS CONVERSAS'}</small><h2 id="cv-project-spotlight-title">{activeProject?.name || activeProject?.title || 'Conversas'}</h2></div><button type="button" onClick={() => setSpotlightOpen(false)} aria-label="Fechar busca"><NavIcon name="close"/></button></header><label className="cv-project-spotlight__input"><NavIcon name="search"/><input ref={spotlightInput} value={spotlightQuery} onChange={event => setSpotlightQuery(event.target.value)} placeholder={projectId ? 'Buscar arquivos, tarefas, atividades…' : 'Buscar conversas…'} aria-label={projectId ? 'Buscar nos itens do projeto' : 'Buscar conversas'}/><kbd>ESC</kbd></label><div className="cv-project-spotlight__results" aria-live="polite">{spotlightQuery.trim().length < 2 ? <p>Digite pelo menos 2 caracteres para iniciar a busca.</p> : spotlightLoading ? <p>Pesquisando…</p> : spotlightError ? <p role="alert">{spotlightError}</p> : spotlightResults.length ? spotlightResults.map(item => item.kind === 'resource' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); if (onOpenLibraryRef) onOpenLibraryRef(`resource:${item.id}`, activeProjectRef).catch(error => { setSpotlightError(error.message || 'Não foi possível abrir este recurso.'); setSpotlightOpen(true); }); else onOpenResource?.({...item, libraryRef:`resource:${item.id}`, project_ref:activeProjectRef}); }}><NavIcon name="file"/><span><b>{item.title}</b><small>{item.detail || 'Recurso do projeto'}</small></span><NavIcon name="chevron"/></button> : item.kind === 'conversation' ? <button type="button" key={`${item.kind}-${item.id}`} onClick={() => { setSpotlightOpen(false); onOpen(String(item.id), item.title); }}><NavIcon name="compose"/><span><b>{item.title}</b><small>{item.detail || 'Conversa do projeto'}</small></span><NavIcon name="chevron"/></button> : <a key={`${item.kind}-${item.id}`} href={item.kind === 'task' ? projectTasksUrl : projectActivityUrl}><NavIcon name={item.kind === 'task' ? 'check' : 'pulse'}/><span><b>{item.title}</b><small>{item.detail || 'Atividade do projeto'}</small></span><NavIcon name="chevron"/></a>) : <p>Nenhum item encontrado{projectId ? ' neste projeto' : ''}.</p>}</div>{projectId && <footer>Arquivos · documentos · tarefas · atividade</footer>}</section></div>, document.getElementById('cadu-conversations-v2-root') || document.body)}
  </>;
}
