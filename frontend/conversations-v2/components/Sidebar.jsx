import React, {useEffect, useMemo, useState} from 'react';
import {Icon} from '../lib/icons';

function contextLabel(item, projects, brands) {
  const project = projects.find(candidate => candidate.ref === item.project_ref);
  if (project) return `Projeto — ${project.name}`;
  const brand = brands.find(candidate => (candidate.ref || candidate.brandRef || `studio:${candidate.id}`) === item.brand_ref);
  return brand ? `Marca — ${brand.name}` : '';
}

export function Sidebar({conversations, projects = [], brands = [], activeId, onOpen, open, onClose, loading, openingId}) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => conversations.filter(item =>
    `${item.title || ''} ${contextLabel(item, projects, brands)}`.toLocaleLowerCase('pt-BR').includes(query.trim().toLocaleLowerCase('pt-BR'))
  ), [conversations, projects, brands, query]);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = event => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

  if (!open) return null;
  return <>
    <button type="button" onClick={onClose} aria-label="Fechar chats recentes" className="cv-recent-backdrop"/>
    <aside id="cv-recent-sidebar" className="cv-recent-sidebar" aria-label="Chats recentes">
      <header className="cv-recent-sidebar__header">
        <div><span>Cadu Chat</span><strong>Recentes</strong></div>
        <div><button type="button" onClick={onClose} aria-label="Recolher chats recentes"><Icon name="chevron" size={16}/></button></div>
      </header>
      {conversations.length > 6 && <label className="cv-recent-search"><Icon name="search" size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversa"/></label>}
      <div className="cv-recent-list">
        {filtered.slice(0, 30).map(item => <button key={item.id} type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined}><span><b>{item.title || 'Conversa sem título'}</b>{contextLabel(item, projects, brands) && <small>{contextLabel(item, projects, brands)}</small>}</span>{String(item.id) === String(openingId) && <i/>}</button>)}
        {loading && !conversations.length && <div className="cv-recent-loading" aria-label="Carregando conversas"><i/><i/><i/></div>}
        {!loading && !filtered.length && <p>{query.trim() ? 'Nenhuma conversa corresponde à busca.' : 'Suas conversas aparecerão aqui.'}</p>}
      </div>
    </aside>
  </>;
}
