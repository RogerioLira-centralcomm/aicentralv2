import React, {useEffect, useMemo, useState} from 'react';
import {Icon} from '../lib/icons';

export function Sidebar({conversations, activeId, onOpen, onNew, open, onClose, loading, openingId}) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => conversations.filter(item =>
    String(item.title || '').toLocaleLowerCase('pt-BR').includes(query.trim().toLocaleLowerCase('pt-BR'))
  ), [conversations, query]);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = event => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

  if (!open) return null;
  return <>
    <button type="button" onClick={onClose} aria-label="Fechar conversas recentes" className="cv-recent-backdrop"/>
    <aside id="cv-recent-sidebar" className="cv-recent-sidebar" aria-label="Conversas recentes">
      <header className="cv-recent-sidebar__header">
        <div><span>Conversas</span><strong>Recentes</strong></div>
        <div><button type="button" onClick={onNew} aria-label="Novo chat"><Icon name="compose" size={16}/></button><button type="button" onClick={onClose} aria-label="Recolher conversas recentes"><Icon name="chevron" size={16}/></button></div>
      </header>
      {conversations.length > 6 && <label className="cv-recent-search"><Icon name="search" size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversa"/></label>}
      <div className="cv-recent-list">
        {filtered.slice(0, 30).map(item => <button key={item.id} type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined}><span>{item.title || 'Conversa sem título'}</span>{String(item.id) === String(openingId) && <i/>}</button>)}
        {loading && !conversations.length && <div className="cv-recent-loading" aria-label="Carregando conversas"><i/><i/><i/></div>}
        {!loading && !filtered.length && <p>{query.trim() ? 'Nenhuma conversa corresponde à busca.' : 'Suas conversas aparecerão aqui.'}</p>}
      </div>
    </aside>
  </>;
}
