import React, {useRef, useState} from 'react';

function AttachIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8.2 12.9 6.5-6.5a3.2 3.2 0 1 1 4.5 4.5l-8.8 8.8a5 5 0 1 1-7-7L12 4"/></svg>;
}

function SendIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6.7 10.3 12 5l5.3 5.3"/></svg>;
}

export function ContextDropZone({children, onContextDrop}) {
  const [active, setActive] = useState(false);
  const drop = event => { event.preventDefault(); setActive(false); const raw = event.dataTransfer.getData('application/x-cadu-item'); if (raw) onContextDrop?.(JSON.parse(raw)); };
  return <div className={`cadu-ds-context-drop ${active ? 'is-active' : ''}`} onDragEnter={() => setActive(true)} onDragLeave={() => setActive(false)} onDragOver={event => event.preventDefault()} onDrop={drop}>{children}</div>;
}

export function WorkspaceComposer({value, onChange, onSubmit, onAttach, context, onClearContext, placeholder = 'Pergunte, crie ou peça uma atualização...', disabled = false, onContextDrop}) {
  const input = useRef(null);
  return <ContextDropZone onContextDrop={onContextDrop}><form className="cadu-ds-composer" onSubmit={event => { event.preventDefault(); onSubmit?.(); }}>
    {context && <div className="cadu-ds-composer-context"><span>{context.label}</span><button type="button" onClick={onClearContext} aria-label="Remover contexto">×</button></div>}
    <button type="button" onClick={onAttach} className="cadu-ds-composer-attach" aria-label="Anexar arquivo"><AttachIcon/></button>
    <textarea ref={input} value={value} onChange={event => onChange?.(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} disabled={disabled} rows="1" placeholder={placeholder} aria-label="Mensagem para o Cadu"/>
    <button type="submit" className="cadu-ds-composer-send" disabled={disabled || !String(value || '').trim()} aria-label="Enviar mensagem"><SendIcon/></button>
  </form></ContextDropZone>;
}
