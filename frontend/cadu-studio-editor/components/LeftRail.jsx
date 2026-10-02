import React, {useEffect, useRef, useState} from 'react';
import {ASSET_DRAG_TYPE} from '../shared';
import {StudioImage} from './StudioImage';

function AssetShelf({title, empty, items, loading, onSelect, open = false, focusable = false}) {
  const ref = useRef(null);
  useEffect(() => {
    if (!focusable) return undefined;
    const focusShelf = () => { if (!ref.current) return; ref.current.open = true; ref.current.scrollIntoView({block: 'start', behavior: 'smooth'}); ref.current.classList.add('is-highlighted'); window.setTimeout(() => ref.current?.classList.remove('is-highlighted'), 1400); ref.current.querySelector('.se-asset-grid button')?.focus({preventScroll: true}); };
    window.addEventListener('cadu:studio-focus-shelf', focusShelf);
    return () => window.removeEventListener('cadu:studio-focus-shelf', focusShelf);
  }, [focusable]);
  return <details ref={ref} className="se-asset-shelf" open={open}><summary><span>{title}</span><b>{loading ? '…' : items.length}</b></summary>{loading ? <p>Carregando imagens…</p> : items.length ? <div className="se-asset-grid">{items.slice(0, 18).map(item => <button type="button" key={item.id || item.url} onClick={() => onSelect(item)} title={`${item.name} · clique ou arraste para o palco`} draggable onDragStart={event => { event.dataTransfer.setData(ASSET_DRAG_TYPE, JSON.stringify(item)); event.dataTransfer.effectAllowed = 'copy'; }}><StudioImage src={item.thumbUrl || item.url} alt={item.name}/><span>{item.name}</span></button>)}</div> : <p>{empty}</p>}</details>;
}

export function LeftRail({versions, selectedId, filter, onFilter, onSelect, onApprove, onSetBase, onRemove = () => {}, onUpload, onNewSession = () => window.dispatchEvent(new Event('cadu:studio-new-session')), onHistory, onRestoreSession = ident => window.dispatchEvent(new CustomEvent('cadu:studio-restore-session', {detail: {ident}})), sessions = [], activeSessionId = '', readOnly, libraryUrl, project, libraryAssets, previousAssets, shelfLoading, onSelectAsset}) {
  const [brokenIds, setBrokenIds] = useState([]);
  const visibleVersions = versions.filter(version => filter === 'all' || (filter === 'review' && version.status !== 'approved') || (filter === 'approved' && version.status === 'approved'));
  return <aside className="se-left-rail" aria-label="Criativos e sessões">
    <section className="se-rail-section">
      <header className="se-session-switcher"><label><span>Sessão de edição</span><select aria-label="Selecionar sessão de edição" value={activeSessionId || ''} onChange={event => event.target.value && onRestoreSession(event.target.value)}><option value="">{versions.length ? 'Sessão local' : 'Nova sessão'}</option>{sessions.map(item => <option key={item.id} value={item.id}>{item.title || 'Sessão sem título'}</option>)}</select></label><button type="button" disabled={readOnly} onClick={onNewSession}>+ Nova</button></header>
      <div className="se-rail-heading"><h2>Versões</h2><button type="button" onClick={onHistory}>Ver histórico</button></div>
      <div className="se-filter"><button className={filter === 'all' ? 'is-active' : ''} type="button" onClick={() => onFilter('all')}>Todos</button><button className={filter === 'review' ? 'is-active' : ''} type="button" onClick={() => onFilter('review')}>A revisar</button><button className={filter === 'approved' ? 'is-active' : ''} type="button" onClick={() => onFilter('approved')}>Aprovadas</button></div>
      <div className="se-rail-list">{visibleVersions.length ? visibleVersions.map(version => <article className={`se-rail-item ${selectedId === version.id ? 'is-selected' : ''} ${brokenIds.includes(version.id) ? 'is-broken' : ''}`} key={version.id}><button className="se-rail-item__select" type="button" onClick={() => onSelect(version.id)}><StudioImage src={version.url} alt={version.name} onUnavailable={() => setBrokenIds(current => current.includes(version.id) ? current : [...current, version.id])}/><span className="se-rail-item__copy"><b>{version.name}</b><small className={`se-status se-status--${version.status}`}>{version.status === 'approved' ? 'Aprovada' : version.status === 'new' ? 'Nova' : 'Rascunho'}</small></span></button>{brokenIds.includes(version.id) && <span className="se-rail-item__actions is-broken"><small>Arquivo não encontrado</small><button type="button" disabled={readOnly} onClick={() => onRemove(version.id)}>Remover</button></span>}{selectedId === version.id && !brokenIds.includes(version.id) && <span className="se-rail-item__actions"><button type="button" disabled={readOnly} onClick={() => onApprove(version.id)}>{version.status === 'approved' ? 'Aprovada' : 'Aprovar'}</button><button type="button" disabled={readOnly} onClick={() => onSetBase(version.id)}>Usar como base</button></span>}</article>) : versions.length ? <p className="se-rail-empty">Nenhuma peça neste filtro.</p> : <button type="button" className="se-upload-empty" onClick={onUpload}>Envie uma peça para começar</button>}</div>
    </section>
    <div className="se-shelves"><AssetShelf title={project ? 'Imagens do projeto' : 'Imagens pessoais'} empty={project ? 'As imagens vinculadas ao projeto aparecerão aqui.' : 'Suas imagens pessoais aparecerão aqui.'} items={libraryAssets} loading={shelfLoading} onSelect={onSelectAsset} open focusable/><AssetShelf title="Anteriores a esta sessão" empty="Nenhuma geração ou edição anterior." items={previousAssets} loading={shelfLoading} onSelect={onSelectAsset}/></div>
    <nav className="se-rail-footer" aria-label="Biblioteca"><a href={libraryUrl || '#'}><span>Biblioteca</span><small>Todos os itens salvos</small></a><button type="button" onClick={onHistory}><span>Sessões anteriores</span><small>Retome uma mesa</small></button></nav>
  </aside>;
}
