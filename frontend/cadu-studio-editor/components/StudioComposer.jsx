import React, {useEffect, useRef} from 'react';

export function StudioComposer({value, onChange, director, onDirectorChange, onGenerate, onAttach, references, onRemoveReference, mask, format, generating, disabled, estimateLabel}) {
  const textarea = useRef(null);
  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${Math.min(150, Math.max(72, element.scrollHeight))}px`;
  }, [value]);
  return <form className="se-composer" onSubmit={event => { event.preventDefault(); onGenerate(); }}>
    <label className="se-composer__label" htmlFor="studio-editor-prompt">O que você quer mudar?</label>
    <textarea id="studio-editor-prompt" ref={textarea} value={value} onChange={event => onChange(event.target.value)} placeholder="Descreva a alteração. Ex.: remova o item marcado e mantenha a iluminação e a identidade visual." maxLength="2000" disabled={disabled || generating}/>
    <div className="se-composer__context">
      {mask && <span className="se-chip">Região marcada <button type="button" onClick={mask.onClear} aria-label="Remover região marcada">×</button></span>}
      <span className="se-chip">Formato {format}</span>
      {references.map((item, index) => <span className="se-reference-chip" key={item.id}><img src={item.dataUrl} alt=""/><button type="button" onClick={() => onRemoveReference(index)} aria-label={`Remover referência ${item.name}`}>×</button></span>)}
      <button className="se-add-reference" type="button" onClick={onAttach} disabled={disabled || generating}>+ Referência</button>
    </div>
    <details className="se-director" open={Boolean(director?.open)} onToggle={event => onDirectorChange({...director, open: event.currentTarget.open})}>
      <summary>Direção do editor</summary>
      <textarea value={director?.objective || ''} onChange={event => onDirectorChange({...director, objective: event.target.value})} placeholder="Ex.: dê prioridade ao produto e use as referências apenas para textura e linguagem visual." maxLength="700" disabled={disabled || generating}/>
      <div>{[['identity','Identidade'],['copy','Textos'],['layout','Composição'],['people','Pessoas']].map(([key,label]) => <label key={key}><input type="checkbox" checked={Boolean(director?.preserve?.includes(key))} onChange={event => onDirectorChange({...director, preserve: event.target.checked ? [...(director?.preserve || []), key] : (director?.preserve || []).filter(item => item !== key)})}/>{label}</label>)}</div>
    </details>
    <footer><label className="se-auto-approve"><input type="checkbox" defaultChecked/> Aprovar por mim</label><span>Direção criativa automática</span><button className="se-generate" type="submit" disabled={disabled || generating || !value.trim()}>{generating ? 'Gerando edição…' : `Gerar edição · ${estimateLabel}`}</button></footer>
  </form>;
}
