import React, {useEffect, useMemo, useState} from 'react';
import {Icon} from '../lib/icons';
import {request, safeUrl} from '../lib/api';

const RESOURCE_GROUPS = [
  {id: 'files', label: 'Arquivos e referências', types: ['file', 'link']},
  {id: 'deliveries', label: 'Entregas e análises', types: ['artifact', 'media_plan', 'report', 'analysis']},
  {id: 'images', label: 'Imagens', types: ['image']},
  {id: 'videos', label: 'Vídeos', types: ['video']},
];

function contextLabel(item, projects, brands) {
  const project = projects.find(candidate => (candidate.ref || candidate.projectRef || candidate.id) === item.project_ref);
  if (project) return project.name;
  const brand = brands.find(candidate => (candidate.ref || candidate.brandRef || `studio:${candidate.id}`) === item.brand_ref);
  return brand ? brand.name : '';
}

function TimerIcon() {
  return <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><circle cx="8" cy="9" r="5.25" fill="none" stroke="currentColor" strokeWidth="1.3"/><path d="M8 9V6.2M6.2 2.1h3.6M11.8 4.2l1-1" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>;
}

export function Sidebar({conversations, projects = [], brands = [], activeProjectRef = '', projectResourcesEndpoint = '/workspace/api/v2/projects', studioLibraryEndpoint = '/workspace/api/v2/studio/library', activeId, onOpen, onOpenResource, onOrganize, onConversationAction, open, onClose, loading, openingId}) {
  const [query, setQuery] = useState('');
  const [actionMenuId, setActionMenuId] = useState('');
  const [resourceState, setResourceState] = useState({projectRef: '', loading: false, resources: [], error: ''});
  const [personalLibrary, setPersonalLibrary] = useState({loading: false, assets: [], error: ''});
  const [rendered, setRendered] = useState(open);
  const [openLibraryGroups, setOpenLibraryGroups] = useState(() => {
    try {
      const raw = document.cookie.match(/(?:^|; )cadu-chat-library-groups=([^;]+)/)?.[1];
      const parsed = raw ? JSON.parse(decodeURIComponent(raw)) : ['logos'];
      return new Set(Array.isArray(parsed) ? parsed : ['logos']);
    } catch (_) { return new Set(['logos']); }
  });
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
    let cancelled = false;
    if (!activeProjectRef || !open) {
      if (!activeProjectRef) setResourceState({projectRef: '', loading: false, resources: [], error: ''});
      return undefined;
    }
    setResourceState({projectRef: activeProjectRef, loading: true, resources: [], error: ''});
    request(`${studioLibraryEndpoint}?project_ref=${encodeURIComponent(activeProjectRef)}`)
      .then(data => {
        if (cancelled) return;
        const brandResources = (data.brand_assets || []).map(asset => ({...asset, id: `brand:${asset.id}`, title: asset.metadata?.display_name || asset.metadata?.original_name || 'Ativo da marca', asset_url: asset.display_url || asset.asset_path || asset.source_url, kind: asset.role === 'logo' ? 'logo' : 'image', source: 'brand'}));
        setResourceState({projectRef: activeProjectRef, loading: false, resources: [...brandResources, ...(data.resources || [])], error: ''});
      })
      .catch(error => {
        if (cancelled) return;
        setResourceState({projectRef: activeProjectRef, loading: false, resources: [], error: error.message || 'Não foi possível carregar os recursos.'});
      });
    return () => { cancelled = true; };
  }, [activeProjectRef, projectResourcesEndpoint, studioLibraryEndpoint, open]);

  useEffect(() => {
    let cancelled = false;
    if (activeProjectRef || !open) return undefined;
    setPersonalLibrary({loading: true, assets: [], error: ''});
    request(`${studioLibraryEndpoint}`)
      .then(data => {
        if (cancelled) return;
        const assets = (data.personal_assets || []).map(asset => ({
          ...asset,
          asset_url: asset.asset_url || asset.image_url || asset.thumb_url,
          title: asset.title || asset.name || 'Criação do Studio',
          kind: asset.kind || 'image',
        }));
        setPersonalLibrary({loading: false, assets, error: ''});
      })
      .catch(error => { if (!cancelled) setPersonalLibrary({loading: false, assets: [], error: error.message || 'Biblioteca indisponível.'}); });
    return () => { cancelled = true; };
  }, [activeProjectRef, open, studioLibraryEndpoint]);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = event => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

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
  const projectResources = resourceState.resources.filter(item => item.source !== 'brand' && item.kind !== 'logo');
  const groupedResources = RESOURCE_GROUPS.map(group => ({...group, resources: projectResources.filter(item => group.types.includes(String(item.type || item.resource_type || 'file')))})).filter(group => group.resources.length);
  const resourceLink = resource => safeUrl(resource.editor_url || resource.download_url || resource.url);
  const studioAsset = resource => {
    const url = safeUrl(resource.asset_url || resource.locator || resource.url);
    if (!url) return null;
    const id = String(resource.id || '');
    const inferredSource = id.startsWith('brand:') ? 'brand' : id.startsWith('reference:') ? 'reference' : id.startsWith('personal:') ? 'personal' : 'studio';
    return {id: resource.id, source_id: resource.source_id || resource.id, source_system: resource.source_system || '', title: resource.title || resource.name || 'Criação do Studio', url, kind: resource.kind || resource.type || resource.resource_type || 'image', source: resource.source || resource.source_system || inferredSource};
  };
  const activeBrand = activeProject && brands.find(item => String(item.ref || item.brandRef || `studio:${item.id}`) === String(activeProject.brand_ref || activeProject.brandRef || ''));
  const entityDetailLink = item => item?.href || '';
  const brandItems = resourceState.resources.filter(item => item.source === 'brand').map(studioAsset).filter(Boolean);
  const libraryItems = activeProject
    ? [...brandItems, ...projectResources.map(studioAsset).filter(Boolean)]
    : personalLibrary.assets.map(studioAsset).filter(Boolean);
  const libraryGroups = [
    {id: 'logos', label: 'Logos da marca', match: item => item.kind === 'logo'},
    {id: 'brand-creatives', label: 'Criativos da marca', match: item => item.kind === 'image' && brandItems.some(brandItem => brandItem.id === item.id)},
    {id: 'created', label: 'Criações', match: item => item.kind === 'image'},
    {id: 'edited', label: 'Edições finais', match: item => /edit|final|approved|aprov/i.test(`${item.title} ${item.kind}`)},
    {id: 'videos', label: 'Vídeos finais', match: item => item.kind === 'video'},
  ].map(group => ({...group, items: libraryItems.filter(group.match)})).filter(group => group.items.length);
  const resourceLabel = resource => resource.type === 'media_plan' ? 'Plano de mídia' : resource.type === 'artifact' ? 'Artefato' : resource.type === 'analysis' ? 'Análise' : resource.mime_type || resource.category || 'Recurso';
  const pinned = filtered.filter(item => item.section === 'pinned');
  const automations = filtered.filter(item => item.section === 'automation');
  const standard = filtered.filter(item => !['pinned', 'automation'].includes(item.section));
  const runAction = (event, item, action) => {
    event.stopPropagation();
    setActionMenuId('');
    onConversationAction?.(item, action);
  };
  const conversationList = (items, hideContext = false) => items.map(item => <div className="cv-conversation-row" key={item.id} draggable onDragStart={event => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('application/x-cadu-conversation', String(item.id)); }}>
    <button className="cv-conversation-card" type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={item.title || 'Conversa sem título'}><span className="cv-conversation-card__copy"><b>{item.title || 'Conversa sem título'}</b>{!hideContext && contextLabel(item, projects, brands) && <small>{contextLabel(item, projects, brands)}</small>}</span><span className={`cv-conversation-card__state ${item.running ? 'is-running' : ''}`} title={item.running ? 'Processo em andamento' : item.section === 'automation' && item.automation_enabled ? 'Automação agendada' : ''}>{item.running ? <i/> : item.section === 'automation' && item.automation_enabled ? <TimerIcon/> : null}</span></button>
    <div className={`cv-conversation-actions ${String(actionMenuId) === String(item.id) ? 'is-open' : ''}`}>
      <button type="button" className="cv-conversation-actions__trigger" aria-label={`Ações de ${item.title || 'conversa'}`} aria-expanded={String(actionMenuId) === String(item.id)} onClick={event => { event.stopPropagation(); setActionMenuId(current => String(current) === String(item.id) ? '' : String(item.id)); }}><span aria-hidden="true">•••</span></button>
      {String(actionMenuId) === String(item.id) && <div className="cv-conversation-actions__menu" role="menu">
        <button type="button" role="menuitem" onClick={event => runAction(event, item, 'toggle-pin')}>{item.section === 'pinned' ? 'Desafixar' : 'Fixar conversa'}</button>
        {item.section === 'automation' && item.automation_enabled && <button type="button" role="menuitem" onClick={event => runAction(event, item, 'stop-automation')}>Encerrar automação</button>}
        <button type="button" role="menuitem" className="is-danger" onClick={event => runAction(event, item, 'archive')}>Arquivar</button>
      </div>}
    </div>
  </div>);
  const dropSection = (section, label, items) => <section className={`cv-conversation-section is-${section}`} onDragOver={event => { if (event.dataTransfer.types.includes('application/x-cadu-conversation')) event.preventDefault(); }} onDrop={event => { event.preventDefault(); const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, section); }}><header><span>{label}</span><b>{items.length || ''}</b></header>{conversationList(items)}</section>;
  const resourceGroup = group => <details key={group.id} open className="cv-project-library__group">
    <summary><span>{group.label}</span><b>{group.resources.length}</b></summary>
    <div>
      {group.resources.slice(0, 6).map(resource => {
        const href = resourceLink(resource);
        const content = <><span className={`cv-project-resource-thumb is-${resource.type || 'file'}`}>{resource.type === 'image' && href ? <img src={href} alt=""/> : resource.type === 'video' ? '▶' : resource.type === 'file' ? '⌁' : '↗'}</span><span><b>{resource.title || 'Recurso sem título'}</b><small>{resourceLabel(resource)}</small></span></>;
        return href ? <a key={resource.id} href={href} target={resource.type === 'link' || resource.url ? '_blank' : undefined} rel="noreferrer">{content}</a> : <span key={resource.id} className="cv-project-resource-row">{content}</span>;
      })}
      {group.resources.length > 6 && activeProject?.href && <a className="cv-project-library__more" href={activeProject.href}>Ver todos</a>}
    </div>
  </details>;
  const rememberLibraryGroup = (groupId, expanded) => setOpenLibraryGroups(current => {
    const next = new Set(current);
    if (expanded) next.add(groupId); else next.delete(groupId);
    document.cookie = `cadu-chat-library-groups=${encodeURIComponent(JSON.stringify([...next]))}; Max-Age=31536000; Path=/; SameSite=Lax`;
    return next;
  });
  const studioGroup = group => <details key={group.id} open={openLibraryGroups.has(group.id)} onToggle={event => rememberLibraryGroup(group.id, event.currentTarget.open)} className={`cv-studio-library__group is-${group.id}`}>
    <summary><span>{group.label}</span><b>{group.items.length}</b></summary>
    <div className="cv-studio-library__grid">{group.items.slice(0, 12).map(item => <button type="button" key={item.id || item.url} className="cv-studio-library__thumb" onClick={() => onOpenResource?.(item)} title={item.title}>
      {item.kind === 'video' ? <span className="cv-studio-library__video">▶</span> : <img src={item.url} alt="" loading="lazy"/>}
      {group.id !== 'logos' && <span>{item.title}</span>}
    </button>)}</div>
  </details>;
  return <>
    <button type="button" onClick={onClose} aria-label="Fechar chats recentes" tabIndex={open ? 0 : -1} className={`cv-recent-backdrop ${open ? 'is-visible' : 'is-closing'}`}/>
    <aside id="cv-recent-sidebar" className={`cv-recent-sidebar ${open ? 'is-open' : 'is-closing'}`} aria-hidden={!open} inert={!open ? true : undefined} aria-label="Chats recentes">
      <header className="cv-recent-sidebar__header">
        <div><span>{activeProject ? 'Projeto ativo' : 'Cadu Chat'}</span><strong>{activeProject?.name || activeProject?.title || 'Recentes'}</strong></div>
        <div><button type="button" onClick={onClose} aria-label="Recolher chats recentes"><Icon name="chevron" size={16}/></button></div>
      </header>
      {conversations.length > 6 && <label className="cv-recent-search"><Icon name="search" size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversa"/></label>}
      <div className="cv-recent-list">
        {dropSection('pinned', 'Conversas fixadas', pinned)}
        {dropSection('automation', 'Automações', automations)}
        {activeProject && <section className="cv-recent-project-section" onDragOver={event => event.preventDefault()} onDrop={event => { const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, 'recent'); }}><header><span>Conversas</span><b>Últimas 10</b></header>{conversationList(projectConversations.filter(item => !['pinned', 'automation'].includes(item.section)), true)}{!loading && !projectConversations.some(item => !['pinned', 'automation'].includes(item.section)) && <p>{query.trim() ? 'Nenhuma conversa deste projeto corresponde à busca.' : 'Ainda não há conversas deste projeto.'}</p>}</section>}
        {activeProject && <section className="cv-project-library" aria-label={`Biblioteca de ${activeProject.name || activeProject.title}`}><header><span>Biblioteca do projeto</span><b>{resourceState.loading ? 'Carregando…' : `${resourceState.resources.length} itens`}</b></header>{resourceState.error && <p>{resourceState.error}</p>}{!resourceState.loading && !resourceState.error && libraryGroups.map(studioGroup)}{!resourceState.loading && !resourceState.error && groupedResources.map(resourceGroup)}{!resourceState.loading && !resourceState.error && !groupedResources.length && !libraryGroups.length && <p>Arquivos, imagens, vídeos e entregas aparecerão aqui quando forem adicionados ao projeto.</p>}</section>}
        {!activeProject && <section className="cv-recent-project-section" onDragOver={event => event.preventDefault()} onDrop={event => { const id = event.dataTransfer.getData('application/x-cadu-conversation'); if (id) onOrganize?.(id, 'recent'); }}><header><span>Conversas recentes</span><b>Últimas 4</b></header>{conversationList(standard.slice(0, 4))}{loading && !conversations.length && <div className="cv-recent-loading" aria-label="Carregando conversas"><i/><i/><i/></div>}{!loading && !filtered.length && <p>{query.trim() ? 'Nenhuma conversa corresponde à busca.' : 'Suas conversas aparecerão aqui.'}</p>}</section>}
        {!activeProject && <section className="cv-project-library cv-personal-library" aria-label="Biblioteca pessoal do Studio"><header><span>Biblioteca pessoal</span><b>{personalLibrary.loading ? 'Carregando…' : `${personalLibrary.assets.length} itens`}</b></header>{personalLibrary.error && <p>{personalLibrary.error}</p>}{!personalLibrary.loading && !personalLibrary.error && libraryGroups.map(studioGroup)}{!personalLibrary.loading && !personalLibrary.error && !libraryGroups.length && <p>Suas criações, edições e vídeos aparecerão aqui.</p>}</section>}
        {activeProject && <details className="cv-recent-all-section"><summary>Outras conversas <b>{otherConversations.length}</b></summary><div>{conversationList(otherConversations.slice(0, 8))}</div></details>}
      </div>
    </aside>
  </>;
}
