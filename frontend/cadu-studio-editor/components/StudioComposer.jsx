import React, {useEffect, useRef, useState} from 'react';
import {StudioModal} from './StudioModal';

const EDIT_SUGGESTIONS = [['Trocar o fundo', 'Troque o fundo mantendo o logo, o título e o assunto principal.'], ['Remover textos extras', 'Remova os textos pequenos e selos, mantendo só o título, o botão e o logo.'], ['Cores da marca', 'Aplique as cores oficiais da marca na peça, sem mudar a composição.'], ['Título legível', 'Deixe o título mais legível, com mais contraste e respiro.']];

export function StudioComposer({value, onChange, director, onDirectorChange, onGenerate, onAttach, references, onRemoveReference, globalReferences = [], onRemoveGlobalReference = () => {}, mask, format, generating, disabled, disabledReason = '', estimateLabel, messages = []}) {
  const textarea = useRef(null);
  const [droppedFile, setDroppedFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${Math.min(150, Math.max(72, element.scrollHeight))}px`;
  }, [value]);
  useEffect(() => {
    let depth = 0;
    const hasImage = event => Array.from(event.dataTransfer?.items || []).some(item => item.kind === 'file' && item.type.startsWith('image/'));
    const enter = event => { if (!hasImage(event)) return; event.preventDefault(); depth += 1; setDragging(true); };
    const over = event => { if (hasImage(event)) { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; } };
    const leave = () => { if (!depth) return; depth = Math.max(0, depth - 1); if (!depth) setDragging(false); };
    const drop = event => {
      const file = Array.from(event.dataTransfer?.files || []).find(item => item.type.startsWith('image/'));
      if (!file) return;
      event.preventDefault(); depth = 0; setDragging(false); setDroppedFile(file);
    };
    window.addEventListener('dragenter', enter); window.addEventListener('dragover', over); window.addEventListener('dragleave', leave); window.addEventListener('drop', drop);
    return () => { window.removeEventListener('dragenter', enter); window.removeEventListener('dragover', over); window.removeEventListener('dragleave', leave); window.removeEventListener('drop', drop); };
  }, []);
  const chooseDrop = action => {
    if (!droppedFile) return;
    window.dispatchEvent(new CustomEvent(`cadu:studio-drop-${action}`, {detail: {file: droppedFile}}));
    setDroppedFile(null);
  };
  return <><form className={`se-composer ${dragging ? 'is-dragging' : ''}`} onSubmit={event => { event.preventDefault(); onGenerate(); }}>
    {messages.length > 0 && <div className="se-agent-thread" aria-live="polite">{messages.slice(-4).map(message => <p key={message.id} className={`is-${message.role}`}>{message.text}</p>)}</div>}
    <textarea id="studio-editor-prompt" ref={textarea} value={value} onChange={event => onChange(event.target.value)} placeholder="Diga ao Cadu o que fazer nesta peça…" maxLength="2000" disabled={disabled || generating} aria-label="Mensagem para o Cadu"/>
    <div className="se-composer__context">
      {mask && <span className="se-chip">Região marcada <button type="button" onClick={mask.onClear} aria-label="Remover região marcada">×</button></span>}
      <span className="se-chip">Formato {format}</span>
      {globalReferences.map(item => <span className="se-reference-chip is-global" key={item.id} title="Referência global do projeto"><img src={item.url} alt=""/><button type="button" onClick={() => onRemoveGlobalReference(item.id)} aria-label="Remover referência global do projeto">×</button></span>)}
      {references.map((item, index) => <span className="se-reference-chip" key={item.id}><img src={item.dataUrl} alt=""/><button type="button" onClick={() => onRemoveReference(index)} aria-label={`Remover referência ${item.name}`}>×</button></span>)}
      <span className="se-drop-hint">Arraste uma imagem para anexar</span>
    </div>
    <details className="se-director" open={Boolean(director?.open)} onToggle={event => onDirectorChange({...director, open: event.currentTarget.open})}>
      <summary>Direção do editor</summary>
      <textarea value={director?.objective || ''} onChange={event => onDirectorChange({...director, objective: event.target.value})} placeholder="Ex.: dê prioridade ao produto e use as referências apenas para textura e linguagem visual." maxLength="700" disabled={disabled || generating}/>
      <div>{[['identity','Identidade'],['copy','Textos'],['layout','Composição'],['people','Pessoas']].map(([key,label]) => <label key={key}><input type="checkbox" checked={Boolean(director?.preserve?.includes(key))} onChange={event => onDirectorChange({...director, preserve: event.target.checked ? [...(director?.preserve || []), key] : (director?.preserve || []).filter(item => item !== key)})}/>{label}</label>)}</div>
    </details>
    {!disabled && !generating && !value.trim() && <div className="se-suggestions" aria-label="Sugestões de edição">{EDIT_SUGGESTIONS.map(([label, text]) => <button type="button" key={label} title={text} onClick={() => { onChange(text); textarea.current?.focus(); }}>{label}</button>)}</div>}
    <footer><button className="se-generate" type="submit" disabled={disabled || generating || !value.trim()}>{generating ? 'Gerando edição…' : `Gerar edição · ${estimateLabel}`}</button>{!generating && (disabled || !value.trim()) && <small className="se-generate-hint" role="status">{disabledReason || 'Descreva a edição para gerar.'}</small>}</footer>
  </form>{dragging && <div className="se-drop-overlay" aria-hidden="true"><strong>Solte a imagem</strong><span>Você escolhe o que fazer em seguida</span></div>}{droppedFile && <StudioModal title="Como usar esta imagem?" onClose={() => setDroppedFile(null)}><div className="se-drop-choice"><p><strong>{droppedFile.name}</strong> não será aplicada até você escolher.</p><button type="button" onClick={() => chooseDrop('reference')} disabled={disabled}><span>Usar como referência</span><small>Mantém a peça e a sessão atuais. A imagem acompanha apenas a próxima geração.</small></button><button type="button" className="is-primary" onClick={() => chooseDrop('replace')}><span>Começar uma nova peça</span><small>Salva este rascunho e inicia outra sessão com a imagem arrastada.</small></button></div></StudioModal>}</>;
}
