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

export function Sidebar({conversations, projects = [], brands = [], activeProjectRef = '', projectResourcesEndpoint = '/workspace/api/v2/projects', activeId, onOpen, open, onClose, loading, openingId}) {
  const [query, setQuery] = useState('');
  const [resourceState, setResourceState] = useState({projectRef: '', loading: false, resources: [], error: ''});
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
    let cancelled = false;
    if (!activeProjectRef || !open) {
      if (!activeProjectRef) setResourceState({projectRef: '', loading: false, resources: [], error: ''});
      return undefined;
    }
    setResourceState({projectRef: activeProjectRef, loading: true, resources: [], error: ''});
    request(`${projectResourcesEndpoint}/${encodeURIComponent(activeProjectRef)}/resources`)
      .then(data => {
        if (cancelled) return;
        setResourceState({projectRef: activeProjectRef, loading: false, resources: data.artifact?.content?.resources || [], error: ''});
      })
      .catch(error => {
        if (cancelled) return;
        setResourceState({projectRef: activeProjectRef, loading: false, resources: [], error: error.message || 'Não foi possível carregar os recursos.'});
      });
    return () => { cancelled = true; };
  }, [activeProjectRef, projectResourcesEndpoint, open]);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = event => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

  if (!rendered) return null;
  const activeProject = projects.find(item => String(item.ref || item.projectRef || item.id) === String(activeProjectRef));
  const projectConversations = filtered.filter(item => String(item.project_ref || '') === String(activeProjectRef)).slice(0, 5);
  const otherConversations = filtered.filter(item => String(item.project_ref || '') !== String(activeProjectRef));
  const groupedResources = RESOURCE_GROUPS.map(group => ({...group, resources: resourceState.resources.filter(item => group.types.includes(String(item.type || item.resource_type || 'file')))})).filter(group => group.resources.length);
  const resourceLink = resource => safeUrl(resource.editor_url || resource.download_url || resource.url);
  const resourceLabel = resource => resource.type === 'media_plan' ? 'Plano de mídia' : resource.type === 'artifact' ? 'Artefato' : resource.type === 'analysis' ? 'Análise' : resource.mime_type || resource.category || 'Recurso';
  const conversationList = (items, hideContext = false) => items.map(item => <button className="cv-conversation-card" key={item.id} type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} title={item.title || 'Conversa sem título'}><span className="cv-conversation-card__copy"><b>{item.title || 'Conversa sem título'}</b>{!hideContext && contextLabel(item, projects, brands) && <small>{contextLabel(item, projects, brands)}</small>}</span>{String(item.id) === String(openingId) && <i/>}</button>);
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
  return <>
    <button type="button" onClick={onClose} aria-label="Fechar chats recentes" tabIndex={open ? 0 : -1} className={`cv-recent-backdrop ${open ? 'is-visible' : 'is-closing'}`}/>
    <aside id="cv-recent-sidebar" className={`cv-recent-sidebar ${open ? 'is-open' : 'is-closing'}`} aria-hidden={!open} inert={!open ? true : undefined} aria-label="Chats recentes">
      <header className="cv-recent-sidebar__header">
        <div><span>{activeProject ? 'Projeto ativo' : 'Cadu Chat'}</span><strong>{activeProject?.name || activeProject?.title || 'Recentes'}</strong></div>
        <div><button type="button" onClick={onClose} aria-label="Recolher chats recentes"><Icon name="chevron" size={16}/></button></div>
      </header>
      {conversations.length > 6 && <label className="cv-recent-search"><Icon name="search" size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversa"/></label>}
      <div className="cv-recent-list">
        {activeProject && <section className="cv-recent-project-section"><header><span>Conversas do projeto</span><b>Últimas 5</b></header>{conversationList(projectConversations, true)}{!loading && !projectConversations.length && <p>{query.trim() ? 'Nenhuma conversa deste projeto corresponde à busca.' : 'Ainda não há conversas neste projeto.'}</p>}</section>}
        {activeProject && <section className="cv-project-library" aria-label={`Biblioteca de ${activeProject.name || activeProject.title}`}><header><span>Biblioteca do projeto</span><b>{resourceState.loading ? 'Carregando…' : `${resourceState.resources.length} itens`}</b></header>{resourceState.error && <p>{resourceState.error}</p>}{!resourceState.loading && !resourceState.error && groupedResources.map(resourceGroup)}{!resourceState.loading && !resourceState.error && !groupedResources.length && <p>Arquivos, imagens, vídeos e entregas aparecerão aqui quando forem adicionados ao projeto.</p>}</section>}
        {!activeProject && <section className="cv-recent-project-section"><header><span>Conversas recentes</span><b>Últimas 5</b></header>{conversationList(filtered.slice(0, 5))}{loading && !conversations.length && <div className="cv-recent-loading" aria-label="Carregando conversas"><i/><i/><i/></div>}{!loading && !filtered.length && <p>{query.trim() ? 'Nenhuma conversa corresponde à busca.' : 'Suas conversas aparecerão aqui.'}</p>}</section>}
        {activeProject && <details className="cv-recent-all-section"><summary>Outras conversas <b>{otherConversations.length}</b></summary><div>{conversationList(otherConversations.slice(0, 8))}</div></details>}
      </div>
    </aside>
  </>;
}
