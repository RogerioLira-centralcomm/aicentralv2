import React, {useEffect, useState} from 'react';
import {Icon} from '../lib/icons';

export function ExecutionQueue({items = [], onUpdate, onRemove, onMove}) {
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');
  useEffect(() => {
    if (editing && !items.some(item => item.id === editing)) setEditing(null);
  }, [editing, items]);
  if (!items.length) return null;
  const save = id => {
    if (draft.trim()) onUpdate?.(id, draft);
    setEditing(null);
  };
  return <section className="cv-execution-queue" aria-label={`${items.length} pedido${items.length === 1 ? '' : 's'} na fila`}>
    <header><span>Na sequência</span><small>{items.length}/5</small></header>
    <ol>
      {items.map((item, index) => <li key={item.id}>
        <span className="cv-execution-queue__order">{index + 1}</span>
        {editing === item.id
          ? <input autoFocus value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') save(item.id); if (event.key === 'Escape') setEditing(null); }} onBlur={() => save(item.id)} aria-label="Editar pedido da fila"/>
          : <button type="button" className="cv-execution-queue__prompt" onClick={() => { setEditing(item.id); setDraft(item.prompt); }} title="Editar pedido">{item.prompt}</button>}
        <div className="cv-execution-queue__actions">
          <button type="button" disabled={index === 0} onClick={() => onMove?.(item.id, -1)} aria-label="Mover pedido para cima"><Icon name="chevron" size={12}/></button>
          <button type="button" disabled={index === items.length - 1} onClick={() => onMove?.(item.id, 1)} aria-label="Mover pedido para baixo"><Icon name="chevron" size={12}/></button>
          <button type="button" onClick={() => onRemove?.(item.id)} aria-label="Remover pedido da fila">×</button>
        </div>
      </li>)}
    </ol>
  </section>;
}
