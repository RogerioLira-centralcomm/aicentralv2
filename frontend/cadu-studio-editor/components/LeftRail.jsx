import React, {useEffect, useRef, useState} from 'react';
import {ASSET_DRAG_TYPE} from '../shared';
import {StudioImage} from './StudioImage';
import {formatBytes, useAssetBytes, useImageDimensions} from '../hooks';


// One section of the rail. Only one is open at a time, so the rail never needs more than one
// short scroll and the open section always has room.
function RailSection({id, title, count, open, onToggle, action, children, sectionRef}) {
  return <section className={`se-rail-block ${open ? 'is-open' : ''}`} ref={sectionRef}>
    <header className="se-rail-block__head">
      <button type="button" className="se-rail-block__toggle" aria-expanded={open} aria-controls={`se-rail-${id}`} onClick={onToggle}>
        <i aria-hidden="true"/><span>{title}</span>{count != null && <b>{count}</b>}
      </button>
      {action}
    </header>
    {open && <div className="se-rail-block__body" id={`se-rail-${id}`}>{children}</div>}
  </section>;
}

function AssetGrid({items, loading, empty, onSelect}) {
  if (loading) return <p className="se-rail-note">Carregando imagens…</p>;
  if (!items.length) return <p className="se-rail-note">{empty}</p>;
  return <div className="se-asset-grid">{items.slice(0, 24).map(item => <button type="button" key={item.id || item.url} onClick={() => onSelect(item)} title={`${item.name} · clique ou arraste para o palco`} draggable onDragStart={event => { event.dataTransfer.setData(ASSET_DRAG_TYPE, JSON.stringify(item)); event.dataTransfer.effectAllowed = 'copy'; }}><StudioImage src={item.thumbUrl || item.url} alt={item.name}/><span>{item.name}</span></button>)}</div>;
}

// Size facts of a version: real pixel size and file weight ("1080 × 1350 · 1,8 MB").
function VersionFacts({url, approved}) {
  const size = useImageDimensions(url);
  const bytes = useAssetBytes(url);
  const parts = [size ? `${size.width} × ${size.height}` : '', formatBytes(bytes)].filter(Boolean);
  return <small className="se-vrow__facts">{approved && <i className="se-vrow__approved" title="Aprovada">✓</i>}{parts.join(' · ') || '…'}</small>;
}

function VersionRow({version, selected, broken, readOnly, selecting, checked, onCheck, onSelect, onApprove, onSetBase, onRemove, onUnavailable}) {
  const approved = version.status === 'approved';
  return <li className={`se-vrow ${selected ? 'is-selected' : ''} ${broken ? 'is-broken' : ''} ${selecting ? 'is-selecting' : ''} ${checked ? 'is-checked' : ''}`}>
    {selecting && <input type="checkbox" className="se-vrow__check" checked={checked} onChange={onCheck} aria-label={`Selecionar ${version.name}`}/>}
    <button type="button" className="se-vrow__main" onClick={selecting ? onCheck : onSelect} aria-current={selected ? 'true' : undefined}>
      <StudioImage src={version.url} alt="" onUnavailable={onUnavailable}/>
      <span className="se-vrow__copy"><b title={version.name}>{version.name}</b>
        {broken ? <small className="se-vrow__facts is-broken">Arquivo não encontrado</small> : <VersionFacts url={version.url} approved={approved}/>}</span>
    </button>
    {!selecting && <span className="se-vrow__actions">
      {broken
        ? <button type="button" disabled={readOnly} onClick={onRemove} title="Remover esta versão">Remover</button>
        : selected && <>
          <button type="button" className={approved ? 'is-done' : 'is-primary'} disabled={readOnly || approved} onClick={onApprove} aria-label={approved ? 'Versão aprovada' : 'Aprovar versão'} title={approved ? 'Aprovada' : 'Aprovar'}>✓</button>
          <button type="button" disabled={readOnly} onClick={onSetBase} aria-label="Usar como base" title="Usar como base da próxima edição">Base</button>
        </>}
    </span>}
  </li>;
}

export function LeftRail({versions, selectedId, onSelect, onApprove, onSetBase, onRemove = () => {}, onRemoveMany = () => {}, onDownload = () => {}, onNewSession = () => window.dispatchEvent(new Event('cadu:studio-new-session')), onHistory, onRestoreSession = ident => window.dispatchEvent(new CustomEvent('cadu:studio-restore-session', {detail: {ident}})), sessions = [], activeSessionId = '', readOnly, libraryUrl, project, libraryAssets, previousAssets, shelfLoading, onSelectAsset}) {
  const [brokenIds, setBrokenIds] = useState([]);
  const [selecting, setSelecting] = useState(false);
  const [checkedIds, setCheckedIds] = useState([]);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [downloading, setDownloading] = useState(false);
  useEffect(() => { setCheckedIds(current => current.filter(id => versions.some(item => item.id === id))); }, [versions]);
  const toggleChecked = id => setCheckedIds(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  const allChecked = versions.length > 0 && checkedIds.length === versions.length;
  const stopSelecting = () => { setSelecting(false); setCheckedIds([]); setConfirmRemove(false); };
  const download = async () => { if (!checkedIds.length) return; setDownloading(true); try { await onDownload(checkedIds); } finally { setDownloading(false); } };
  const [open, setOpen] = useState(versions.length ? 'versions' : 'project');
  const projectRef = useRef(null);
  const hadVersions = useRef(versions.length > 0);
  const toggle = id => setOpen(current => current === id ? null : id);

  // With nothing to edit the project images are what the person needs; once there is a piece, the versions are.
  useEffect(() => {
    if (versions.length && !hadVersions.current) setOpen('versions');
    if (!versions.length && hadVersions.current) setOpen('project');
    hadVersions.current = versions.length > 0;
  }, [versions.length]);

  // "Usar imagem do projeto" in the empty stage opens and highlights the project images.
  useEffect(() => {
    const focusShelf = () => {
      setOpen('project');
      window.setTimeout(() => { projectRef.current?.scrollIntoView({block: 'start', behavior: 'smooth'}); projectRef.current?.querySelector('.se-asset-grid button')?.focus({preventScroll: true}); }, 40);
    };
    window.addEventListener('cadu:studio-focus-shelf', focusShelf);
    return () => window.removeEventListener('cadu:studio-focus-shelf', focusShelf);
  }, []);

  // Picking an image opens it on the stage and folds the picker away.
  const pick = item => { onSelectAsset(item); setOpen('versions'); };
  const projectTitle = project ? 'Imagens do projeto' : 'Imagens pessoais';

  return <aside className="se-left-rail" aria-label="Versões e imagens">
    <header className="se-rail-top">
      <select aria-label="Sessão de edição" value={activeSessionId || ''} onChange={event => event.target.value && onRestoreSession(event.target.value)}>
        <option value="">{versions.length ? 'Sessão local' : 'Nova sessão'}</option>
        {sessions.map(item => <option key={item.id} value={item.id}>{item.title || 'Sessão sem título'}</option>)}
      </select>
      <button type="button" disabled={readOnly} onClick={onNewSession}>+ Nova</button>
    </header>
    <div className="se-rail-scroll">
      <RailSection id="versions" title="Versões" count={versions.length} open={open === 'versions'} onToggle={() => toggle('versions')}
        action={versions.length ? <span className="se-rail-block__links">{!selecting && <button type="button" className="se-rail-block__link" onClick={() => { setOpen('versions'); setSelecting(true); }}>Selecionar</button>}<button type="button" className="se-rail-block__link" onClick={onHistory}>Histórico</button></span> : <button type="button" className="se-rail-block__link" onClick={onHistory}>Histórico</button>}>
        {selecting && <div className="se-select-bar" role="toolbar" aria-label="Ações nas versões selecionadas">
          <label><input type="checkbox" checked={allChecked} onChange={() => setCheckedIds(allChecked ? [] : versions.map(item => item.id))}/>Todas</label>
          <button type="button" disabled={!checkedIds.length || downloading} onClick={download}>{downloading ? 'Preparando…' : `Baixar${checkedIds.length ? ` (${checkedIds.length})` : ''}`}</button>
          <button type="button" className="is-danger" disabled={!checkedIds.length || readOnly} onClick={() => setConfirmRemove(true)}>Remover{checkedIds.length ? ` (${checkedIds.length})` : ''}</button>
          <button type="button" className="se-select-bar__close" onClick={stopSelecting} aria-label="Sair da seleção">×</button>
        </div>}
        {confirmRemove && <div className="se-confirm" role="alertdialog" aria-label="Confirmar remoção"><p>Remover {checkedIds.length} {checkedIds.length === 1 ? 'versão' : 'versões'} desta sessão? As imagens continuam salvas na Biblioteca.</p><span><button type="button" onClick={() => setConfirmRemove(false)}>Cancelar</button><button type="button" className="is-danger" onClick={() => { onRemoveMany(checkedIds); stopSelecting(); }}>Remover</button></span></div>}
        {versions.length
          ? <ul className="se-version-list">{versions.map(version => <VersionRow key={version.id} version={version} selected={selectedId === version.id} broken={brokenIds.includes(version.id)} readOnly={readOnly} selecting={selecting} checked={checkedIds.includes(version.id)} onCheck={() => toggleChecked(version.id)}
              onSelect={() => onSelect(version.id)} onApprove={() => onApprove(version.id)} onSetBase={() => onSetBase(version.id)} onRemove={() => onRemove(version.id)}
              onUnavailable={() => setBrokenIds(current => current.includes(version.id) ? current : [...current, version.id])}/>)}</ul>
          : <p className="se-rail-note">Envie uma peça ou escolha uma imagem do projeto para começar.</p>}
      </RailSection>
      <RailSection id="project" title={projectTitle} count={shelfLoading ? '…' : libraryAssets.length} open={open === 'project'} onToggle={() => toggle('project')} sectionRef={projectRef}>
        <AssetGrid items={libraryAssets} loading={shelfLoading} empty={project ? 'As imagens vinculadas ao projeto aparecerão aqui.' : 'Suas imagens pessoais aparecerão aqui.'} onSelect={pick}/>
      </RailSection>
      <RailSection id="previous" title="Anteriores a esta sessão" count={shelfLoading ? '…' : previousAssets.length} open={open === 'previous'} onToggle={() => toggle('previous')}>
        <AssetGrid items={previousAssets} loading={shelfLoading} empty="Nenhuma geração ou edição anterior." onSelect={pick}/>
      </RailSection>
    </div>
    <nav className="se-rail-foot" aria-label="Atalhos">
      <a href={libraryUrl || '#'}>Biblioteca<i aria-hidden="true">›</i></a>
      <button type="button" onClick={onHistory}>Sessões anteriores<i aria-hidden="true">›</i></button>
    </nav>
  </aside>;
}
