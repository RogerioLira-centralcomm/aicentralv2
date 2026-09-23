import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {acceptStudioSessionAsset, attachStudioSessionProject, continueStudioSession, createStudioSession, finalizeStudioSession, finalizeStudioSessionOnExit, listStudioSessions, loadProjectContexts, loadProjectCreationHistory, loadStudioLibrary, readStudioSession, requestEdition as requestEditorEdition, requestQuote, saveStudioSession, uploadStudioAsset} from './api';
import {MaskCanvas} from './components/MaskCanvas';
import {StudioComposer} from './components/StudioComposer';
import {StudioModal} from './components/StudioModal';

const FORMATS = ['4:5', '1:1', '9:16', '16:9'];
const FORMAT_SIZES = {'4:5': {width: 1080, height: 1350}, '1:1': {width: 1080, height: 1080}, '9:16': {width: 1080, height: 1920}, '16:9': {width: 1920, height: 1080}};
const outputSizeFor = format => ({...(FORMAT_SIZES[format] || FORMAT_SIZES['4:5']), format});
const STORAGE_PREFIX = 'cadu-studio-editor-v1';
const makeId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
const makeDirectorInstruction = (prompt, director) => [prompt, director?.objective && `Direção do editor: ${director.objective}`, director?.preserve?.length && `Preserve rigorosamente: ${director.preserve.join(', ')}.`, 'Use referências visuais apenas por similaridade; preserve a identidade da peça-base.'].filter(Boolean).join('\n\n');

function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Não foi possível abrir a imagem.'));
    reader.readAsDataURL(file);
  });
}

function imageSize(url) {
  return new Promise(resolve => {
    const image = new Image();
    image.onload = () => resolve({width: image.naturalWidth || 1600, height: image.naturalHeight || 900});
    image.onerror = () => resolve({width: 1600, height: 900});
    image.src = url;
  });
}

function browserImageUrl(value) {
  const raw = String(value || '').trim();
  if (!raw || raw.startsWith('data:') || raw.startsWith('blob:')) return raw;
  try {
    const parsed = new URL(raw, window.location.origin);
    if (parsed.pathname.startsWith('/static/') || parsed.pathname.startsWith('/parametros/')) return `${window.location.origin}${parsed.pathname}${parsed.search}`;
    return parsed.href;
  } catch {
    return raw;
  }
}

function StudioImage({src, alt = '', className = ''}) {
  const [failed, setFailed] = useState(false);
  const resolvedSrc = browserImageUrl(src);
  useEffect(() => setFailed(false), [resolvedSrc]);
  if (!resolvedSrc || failed) return <span className={`se-image-fallback ${className}`} role="img" aria-label={alt}>Imagem indisponível</span>;
  return <img className={className} src={resolvedSrc} alt={alt} onError={() => setFailed(true)} />;
}

function AssetShelf({title, empty, items, loading, onSelect, open = false}) {
  return <details className="se-asset-shelf" open={open}><summary><span>{title}</span><b>{loading ? '…' : items.length}</b></summary>{loading ? <p>Carregando imagens…</p> : items.length ? <div className="se-asset-grid">{items.slice(0, 18).map(item => <button type="button" key={item.id || item.url} onClick={() => onSelect(item)} title={item.name}><StudioImage src={item.thumbUrl || item.url} alt={item.name}/><span>{item.name}</span></button>)}</div> : <p>{empty}</p>}</details>;
}

function LeftRail({versions, selectedId, filter, onFilter, onSelect, onApprove, onSetBase, onUpload, onNewSession = () => window.dispatchEvent(new Event('cadu:studio-new-session')), onHistory, onRestoreSession = ident => window.dispatchEvent(new CustomEvent('cadu:studio-restore-session', {detail: {ident}})), sessions = [], activeSessionId = '', readOnly, libraryUrl, project, libraryAssets, previousAssets, shelfLoading, onSelectAsset}) {
  const visibleVersions = versions.filter(version => filter === 'all' || (filter === 'review' && version.status !== 'approved') || (filter === 'approved' && version.status === 'approved'));
  return <aside className="se-left-rail" aria-label="Criativos e sessões">
    <section className="se-rail-section">
      <header className="se-session-switcher"><label><span>Sessão de edição</span><select aria-label="Selecionar sessão de edição" value={activeSessionId || ''} onChange={event => event.target.value && onRestoreSession(event.target.value)}><option value="">{versions.length ? 'Sessão local' : 'Nova sessão'}</option>{sessions.map(item => <option key={item.id} value={item.id}>{item.title || 'Sessão sem título'}</option>)}</select></label><button type="button" disabled={readOnly} onClick={onNewSession}>+ Nova</button></header>
      <div className="se-rail-heading"><h2>Versões</h2><button type="button" onClick={onHistory}>Ver histórico</button></div>
      <div className="se-filter"><button className={filter === 'all' ? 'is-active' : ''} type="button" onClick={() => onFilter('all')}>Todos</button><button className={filter === 'review' ? 'is-active' : ''} type="button" onClick={() => onFilter('review')}>A revisar</button><button className={filter === 'approved' ? 'is-active' : ''} type="button" onClick={() => onFilter('approved')}>Aprovadas</button></div>
      <div className="se-rail-list">{visibleVersions.length ? visibleVersions.map(version => <article className={`se-rail-item ${selectedId === version.id ? 'is-selected' : ''}`} key={version.id}><button className="se-rail-item__select" type="button" onClick={() => onSelect(version.id)}><StudioImage src={version.url} alt={version.name}/><span className="se-rail-item__copy"><b>{version.name}</b><small className={`se-status se-status--${version.status}`}>{version.status === 'approved' ? 'Aprovada' : version.status === 'new' ? 'Nova' : 'Rascunho'}</small></span></button>{selectedId === version.id && <span className="se-rail-item__actions"><button type="button" disabled={readOnly} onClick={() => onApprove(version.id)}>{version.status === 'approved' ? 'Aprovada' : 'Aprovar'}</button><button type="button" disabled={readOnly} onClick={() => onSetBase(version.id)}>Usar como base</button></span>}</article>) : versions.length ? <p className="se-rail-empty">Nenhuma peça neste filtro.</p> : <button type="button" className="se-upload-empty" onClick={onUpload}>Envie uma peça para começar</button>}</div>
    </section>
    <div className="se-shelves"><AssetShelf title={project ? 'Imagens do projeto' : 'Imagens pessoais'} empty={project ? 'As imagens vinculadas ao projeto aparecerão aqui.' : 'Suas imagens pessoais aparecerão aqui.'} items={libraryAssets} loading={shelfLoading} onSelect={onSelectAsset} open/><AssetShelf title="Anteriores a esta sessão" empty="Nenhuma geração ou edição anterior." items={previousAssets} loading={shelfLoading} onSelect={onSelectAsset}/></div>
    <nav className="se-rail-footer" aria-label="Biblioteca"><a href={libraryUrl || '#'}><span>Biblioteca</span><small>Todos os itens salvos</small></a><button type="button" onClick={onHistory}><span>Sessões anteriores</span><small>Retome uma mesa</small></button></nav>
  </aside>;
}

function StudioTopbar({links, projects, project, onProjectChange, bootstrap, sessionName = 'Nova sessão de edição', onHistory = () => window.dispatchEvent(new Event('cadu:studio-history')), onNewSession = () => window.dispatchEvent(new Event('cadu:studio-new-session'))}) {
  const initials = String(bootstrap.user?.name || 'C').split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
  return <header className="se-topbar">
    <a className="se-brand" href={links.home || '#'}><img src="/static/images/cadu/brand-icons/studio-192.png" alt=""/><strong>Cadu</strong><span>Studio</span></a>
    <nav>{[['Criar', links.create], ['Editor', links.editor], ['Vídeos', links.videos], ['Áudio', links.audio], ['Analyzer', links.analyzer], ['Biblioteca', links.library]].map(([label, href]) => <a key={label} href={href || '#'} className={label === 'Editor' ? 'is-active' : ''}>{label}</a>)}</nav><div className="se-session-nav"><span>Sessão de edição</span><strong title={sessionName}>{sessionName}</strong><button type="button" onClick={onHistory}>Histórico</button><button type="button" className="is-new" onClick={onNewSession}>+ Nova</button></div>
    <label className="se-project-picker"><span>Projeto e marca</span><select value={project?.id || ''} onChange={event => onProjectChange(event.target.value)}><option value="">Selecionar projeto</option>{projects.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
    <a className="se-credit-meter" href={links.credits || '#'} aria-label="Abrir consumo e uso de créditos"><span>Uso e créditos</span><strong>{Number(bootstrap.credits || 0).toLocaleString('pt-BR')}</strong><i><b style={{width: `${Math.min(100, Number(bootstrap.usagePercent || 0))}%`}}/></i></a>
    <a className="se-account-link" href={links.profile || links.workspace || '#'} aria-label="Abrir página da conta">{bootstrap.user?.avatar ? <img src={bootstrap.user.avatar} alt=""/> : <span>{initials || 'C'}</span>}</a>
  </header>;
}

function BrandPanel({format, setFormat, status, project, selectedGlobalReferences, onGlobalReferencesChange, batchProgress, onPauseQueue, onCancelQueue, onResumeQueue, readOnly, onHistory, onFinalize, onContinue, onExpand, composer}) {
  const [drawer, setDrawer] = useState(null);
  const brand = project?.brand_context || {};
  const brandFonts = brand.fonts || brand.profile?.fonts || [];
  const globalReferences = (brand.assets?.references || []).map((url, index) => ({id: `brand-reference-${index}`, url, label: `Referência global ${index + 1}`}));
  const selectedCount = selectedGlobalReferences.length;
  return <aside className="se-right-panel" aria-label="Assistente, projeto, marca e entrega">
    <header className="se-project-head"><div><span>Projeto e marca</span><strong>Contexto do projeto</strong></div><div className="se-session-actions"><span className={`se-save-state is-${status}`}>{readOnly ? 'Sessão finalizada' : status === 'saving' ? 'Salvando rascunho' : status === 'synced' ? 'Sessão sincronizada' : 'Rascunho local'}</span><button type="button" onClick={onHistory}>Histórico</button>{readOnly ? <button type="button" onClick={onContinue}>Continuar</button> : <button type="button" onClick={onFinalize}>Finalizar</button>}</div></header>
    <section className="se-panel-section se-assistant-content">{composer}</section>
    <section className="se-panel-section se-brand-content"><h2>Marca</h2><span className="se-brand-label">Cores</span>{brand.palette?.length ? <div className="se-brand-swatches">{brand.palette.slice(0, 5).map(color => <i key={typeof color === 'string' ? color : color.hex} style={{background: typeof color === 'string' ? color : color.hex}} title={typeof color === 'string' ? color : color.hex}/>)}</div> : <span className="se-brand-empty">Selecione um projeto para carregar as cores.</span>}<span className="se-brand-label">Tipografia</span><strong className="se-type-preview">{brandFonts.length ? brandFonts.slice(0, 2).map(font => typeof font === 'string' ? font : font.family).filter(Boolean).join(' · ') : 'Tipografia não definida'}</strong><button type="button" className="se-text-button" onClick={() => setDrawer('guidelines')}>Abrir diretrizes</button></section>
    <section className="se-panel-section se-delivery-content"><h2>Entrega</h2><label>Formato<div className="se-format-options">{FORMATS.map(item => <button type="button" key={item} className={format === item ? 'is-active' : ''} onClick={() => setFormat(item)}>{item}</button>)}</div></label>{batchProgress && batchProgress.status !== 'completed' && <div className="se-queue-state"><strong>Fila: {batchProgress.completed}/{batchProgress.total}</strong><span>Gerando uma peça por vez.</span></div>}</section>
    {drawer === 'guidelines' && <StudioModal title="Diretrizes da marca" onClose={() => setDrawer(null)}><div className="se-brand-drawer"><p>{brand.brand_summary || 'Nenhuma diretriz descritiva foi cadastrada para esta marca.'}</p>{brand.creative_guidelines?.length ? <section><h3>Direção criativa</h3><ul>{brand.creative_guidelines.map(item => <li key={item}>{item}</li>)}</ul></section> : null}{brand.mandatory_elements?.length ? <section><h3>Obrigatórios</h3><ul>{brand.mandatory_elements.map(item => <li key={item}>{item}</li>)}</ul></section> : null}{brand.forbidden_elements?.length ? <section><h3>Evitar</h3><ul>{brand.forbidden_elements.map(item => <li key={item}>{item}</li>)}</ul></section> : null}</div></StudioModal>}
    {drawer === 'references' && <StudioModal title="Referências globais" onClose={() => setDrawer(null)}><div className="se-brand-drawer"><p>Escolha quais referências devem acompanhar esta edição. Elas orientam similaridade visual e não substituem a peça-base.</p>{globalReferences.length ? <div className="se-global-reference-list">{globalReferences.map(reference => <label key={reference.id}><input type="checkbox" checked={selectedGlobalReferences.includes(reference.id)} onChange={() => onGlobalReferencesChange(selectedGlobalReferences.includes(reference.id) ? selectedGlobalReferences.filter(id => id !== reference.id) : [...selectedGlobalReferences, reference.id])}/><img src={reference.url} alt=""/><span>{reference.label}</span></label>)}</div> : <p>Nenhuma referência global disponível neste projeto.</p>}</div></StudioModal>}
  </aside>;
}

function CanvasWorkspace({asset, mode, setMode, mask, crop, maskRef, onMaskChange, onCropChange, onUpload, format, onUndo, onRedo, canUndo, canRedo, outputSize, onOutputSizeChange, zoom = 100, onZoomChange = () => {}, quality = 'draft', onQualityChange = () => {}, onRemoveBackground = () => {}}) {
  const [size, setSize] = useState({width: 1600, height: 900});
  const [cropDrag, setCropDrag] = useState(null);
  useEffect(() => { if (asset?.url) imageSize(asset.url).then(setSize); }, [asset?.url]);
  const cropBounds = crop?.bounds || [Math.round(size.width * .16), Math.round(size.height * .12), Math.round(size.width * .68), Math.round(size.height * .76)];
  const applyCrop = () => { onCropChange({bounds: cropBounds}); setMode('select'); };
  const cropStyle = {left: `${(cropBounds[0] / size.width) * 100}%`, top: `${(cropBounds[1] / size.height) * 100}%`, width: `${(cropBounds[2] / size.width) * 100}%`, height: `${(cropBounds[3] / size.height) * 100}%`};
  const moveCrop = event => { if (!cropDrag) return; const rect = event.currentTarget.getBoundingClientRect(); const dx = ((event.clientX - cropDrag.x) / rect.width) * size.width; const dy = ((event.clientY - cropDrag.y) / rect.height) * size.height; let [x, y, width, height] = cropDrag.bounds; const minSize = Math.min(96, size.width * .15, size.height * .15); if (cropDrag.action === 'move') { x = Math.max(0, Math.min(size.width - width, x + dx)); y = Math.max(0, Math.min(size.height - height, y + dy)); } else { const edge = cropDrag.action; if (edge.includes('e')) width = Math.max(minSize, Math.min(size.width - x, width + dx)); if (edge.includes('s')) height = Math.max(minSize, Math.min(size.height - y, height + dy)); if (edge.includes('w')) { const nextX = Math.max(0, Math.min(x + width - minSize, x + dx)); width += x - nextX; x = nextX; } if (edge.includes('n')) { const nextY = Math.max(0, Math.min(y + height - minSize, y + dy)); height += y - nextY; y = nextY; } } onCropChange({bounds: [Math.round(x), Math.round(y), Math.round(width), Math.round(height)]}); };
  const beginCrop = (event, action) => { event.preventDefault(); event.stopPropagation(); event.currentTarget.setPointerCapture?.(event.pointerId); setCropDrag({action, x: event.clientX, y: event.clientY, bounds: cropBounds}); };
  return <section className="se-workspace"><div className="se-toolbar" role="toolbar" aria-label="Ferramentas de edição"><div className="se-tool-group"><button className={mode === 'select' ? 'is-active' : ''} type="button" onClick={() => setMode('select')}>Selecionar</button><button className={mode === 'mask' ? 'is-active' : ''} type="button" onClick={() => setMode('mask')}>Marcar região</button><button className={mode === 'crop' ? 'is-active' : ''} type="button" onClick={() => setMode('crop')}>Cortar</button><button type="button" onClick={onRemoveBackground}>Remover fundo</button></div><span/><label className="se-size-field"><span>L</span><input aria-label="Largura" type="number" min="256" max="4096" value={outputSize.width} onChange={event => onOutputSizeChange({...outputSize, width: Number(event.target.value)})}/></label><b>×</b><label className="se-size-field"><span>A</span><input aria-label="Altura" type="number" min="256" max="4096" value={outputSize.height} onChange={event => onOutputSizeChange({...outputSize, height: Number(event.target.value)})}/></label><label className="se-output-picker"><span>Saída</span><select value={quality} onChange={event => onQualityChange(event.target.value)}><option value="draft">Baixa</option><option value="standard">Padrão</option><option value="high">Alta</option></select></label><span/><button type="button" disabled={!canUndo} onClick={onUndo} aria-label="Desfazer">↶</button><button type="button" disabled={!canRedo} onClick={onRedo} aria-label="Refazer">↷</button><button type="button" onClick={() => onZoomChange(Math.max(50, zoom - 10))} aria-label="Reduzir zoom">−</button><button type="button" onClick={() => onZoomChange(Math.min(150, zoom + 10))} aria-label="Aumentar zoom">＋</button><button type="button" onClick={() => onZoomChange(100)}>{zoom}%</button></div><div className={`se-stage ${asset ? 'has-asset' : ''}`}>{asset ? <div className="se-artboard" style={{aspectRatio: `${size.width} / ${size.height}`, transform: `scale(${zoom / 100})`}} onPointerMove={moveCrop} onPointerUp={() => setCropDrag(null)} onPointerCancel={() => setCropDrag(null)}><StudioImage src={asset.url} alt="Criativo em edição"/><MaskCanvas ref={maskRef} active={mode === 'mask'} width={size.width} height={size.height} onChange={onMaskChange}/>{mask && mode !== 'mask' && <span className="se-mask-note">Região marcada</span>}{crop && mode !== 'crop' && <span className="se-crop-note">Corte aplicado</span>}{mode === 'crop' && <><div className="se-crop-frame" style={cropStyle} onPointerDown={event => beginCrop(event, 'move')}><span>Arraste para mover</span>{['nw', 'ne', 'se', 'sw'].map(edge => <button key={edge} type="button" aria-label={`Redimensionar corte ${edge}`} className={`se-crop-handle is-${edge}`} onPointerDown={event => beginCrop(event, edge)}/>)}</div><div className="se-mask-tools"><span>Arraste a moldura ou as alças para definir o enquadramento</span><button type="button" onClick={() => { onCropChange(null); setMode('select'); }}>Limpar</button><button type="button" onClick={applyCrop}>Aplicar corte</button></div></>}{mode === 'mask' && <div className="se-mask-tools"><span>Desenhe sobre a área a alterar</span><button type="button" onClick={() => maskRef.current?.clear()}>Limpar</button><button type="button" onClick={() => { onMaskChange(maskRef.current?.exportMask()); setMode('select'); }}>Concluir máscara</button></div>}</div> : <button type="button" className="se-upload-stage" onClick={onUpload}><i aria-hidden="true">＋</i><strong>Adicione uma imagem ao palco</strong><span>PNG, JPG ou WebP · até 20 MB</span></button>}</div></section>;
}

function ExpandDialog({asset, onClose, onQueue, onQuote}) {
  const [count, setCount] = useState(4);
  const [formats, setFormats] = useState(new Set(['4:5', '1:1']));
  const [queued, setQueued] = useState(false);
  const [estimate, setEstimate] = useState(null);
  const toggle = value => setFormats(current => { const next = new Set(current); next.has(value) ? next.delete(value) : next.add(value); return next; });
  useEffect(() => { let active = true; setEstimate(null); onQuote({count, formats: [...formats]}).then(value => { if (active) setEstimate(value); }).catch(() => { if (active) setEstimate(false); }); return () => { active = false; }; }, [count, formats, onQuote]);
  const prepare = async () => { if (!formats.size || queued) return; setQueued(true); try { await onQueue({count, formats: [...formats]}); onClose(); } finally { setQueued(false); } };
  const estimateLabel = estimate === null ? 'Calculando estimativa…' : estimate === false ? 'Não foi possível calcular a estimativa.' : `${Number(estimate).toLocaleString('pt-BR')} créditos estimados para ${count} peças.`;
  return <StudioModal title="Desdobrar formatos" onClose={onClose}><div className="se-expand-dialog"><div className="se-expand-base">{asset && <img src={asset.url} alt="Peça base"/>}<div><strong>Peça-base</strong><span>Esta versão será usada como referência em todas as saídas.</span></div></div><div><h3>Formatos</h3><div className="se-format-options">{FORMATS.map(item => <button type="button" key={item} className={formats.has(item) ? 'is-active' : ''} onClick={() => toggle(item)}>{item}</button>)}</div></div><div className="se-expand-quantity"><span>Quantidade de peças</span><button type="button" onClick={() => setCount(value => Math.max(1, value - 1))}>−</button><strong>{count}</strong><button type="button" onClick={() => setCount(value => Math.min(30, value + 1))}>+</button><small>Uma geração por vez, sempre a partir da peça-base.</small></div><footer><span>{estimateLabel}</span><button type="button" disabled={!formats.size || queued || estimate === null || estimate === false} onClick={prepare}>{queued ? 'Preparando…' : 'Preparar fila'}</button></footer></div></StudioModal>;
}

export default function StudioEditorApp({bootstrap}) {
  const storageKey = `${STORAGE_PREFIX}:${bootstrap.clientId || 'default'}`;
  const initial = useMemo(() => { try { return JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch { return {}; } }, [storageKey]);
  const handoff = useMemo(() => {
    const query = new URLSearchParams(window.location.search);
    const source = query.get('source_url') || '';
    let url = '';
    try { const parsed = new URL(source, window.location.origin); if (['http:', 'https:'].includes(parsed.protocol)) url = parsed.href; } catch (_) {}
    return url ? {id: 'workspace-handoff', url, name: query.get('source_title') || 'Imagem de referência', status: 'draft', source: 'workspace'} : null;
  }, []);
  const initialAsset = handoff || initial.asset || null;
  const initialVersions = handoff ? [handoff] : initial.versions || [];
  const initialQuery = new URLSearchParams(window.location.search);
  const initialMode = initialQuery.get('editor_mode');
  const [asset, setAsset] = useState(initialAsset);
  const [versions, setVersions] = useState(initialVersions);
  const [selectedId, setSelectedId] = useState(handoff?.id || initial.selectedId || '');
  const [prompt, setPrompt] = useState(initialQuery.get('instruction') || initial.prompt || '');
  const [director, setDirector] = useState({open: false, objective: '', preserve: ['identity', 'copy', 'layout']});
  const [batchProgress, setBatchProgress] = useState(null);
  const [format, setFormat] = useState(initial.format || '4:5');
  const [quality, setQuality] = useState(initial.quality || 'draft');
  const [zoom, setZoom] = useState(initial.zoom || 100);
  const [outputSize, setOutputSize] = useState(() => initial.outputSize ? {...initial.outputSize, format: initial.outputSize.format || initial.format || '4:5'} : outputSizeFor(initial.format || '4:5'));
  const [mode, setMode] = useState(['select', 'mask', 'crop', 'format'].includes(initialMode) ? initialMode : 'select');
  const [mask, setMask] = useState(initial.mask || null);
  const [crop, setCrop] = useState(initial.crop || null);
  const [references, setReferences] = useState([]);
  const [selectedGlobalReferences, setSelectedGlobalReferences] = useState(initial.selectedGlobalReferences || []);
  const [railFilter, setRailFilter] = useState('all');
  const [status, setStatus] = useState('local');
  const [studioSession, setStudioSession] = useState(null);
  const [project, setProject] = useState(null);
  const [personalClientId, setPersonalClientId] = useState('');
  const [projects, setProjects] = useState([]);
  const [sessionHistory, setSessionHistory] = useState([]);
  const [libraryAssets, setLibraryAssets] = useState([]);
  const [previousAssets, setPreviousAssets] = useState([]);
  const [shelfLoading, setShelfLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [estimate, setEstimate] = useState(null);
  const [notice, setNotice] = useState('');
  const [agentMessages, setAgentMessages] = useState(initial.agentMessages || []);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [expandOpen, setExpandOpen] = useState(false);
  const [conflictOpen, setConflictOpen] = useState(false);
  useEffect(() => {
    const openExpand = () => setExpandOpen(true);
    window.addEventListener('cadu:studio-expand', openExpand);
    return () => window.removeEventListener('cadu:studio-expand', openExpand);
  }, []);
  const fileInput = useRef(null);
  const referenceInput = useRef(null);
  const maskRef = useRef(null);
  const studioSessionRef = useRef(null);
  const startedAt = useRef(Date.now());
  const queueControl = useRef({pause: false, cancel: false});
  const editorUndo = useRef([]);
  const editorRedo = useRef([]);
  const lastEditorSnapshot = useRef('');
  const restoringHistory = useRef(false);
  const recordedGenerations = useRef(new Set());
  const [historyState, setHistoryState] = useState({undo: false, redo: false});
  const requestEdition = useCallback(args => requestEditorEdition({...args, sessionId: studioSessionRef.current?.id || ''}), []);
  const selected = versions.find(item => item.id === selectedId) || versions[0] || null;
  const clientId = project?.client_id || bootstrap.clientId || personalClientId || '';

  useEffect(() => {
    loadProjectContexts({apiRoot: bootstrap.apiRoot}).then(data => {
      const contexts = data.items || [];
      setProjects(contexts);
      const requested = String(bootstrap.projectId || '').replace(/^ci:/, '');
      const match = contexts.find(item => [item.id, item.external_project_id].some(id => String(id || '').replace(/^ci:/, '') === requested));
      setProject(match || null);
    }).catch(() => { setProjects([]); setProject(null); });
  }, [bootstrap.apiRoot, bootstrap.clientId, bootstrap.projectId]);

  useEffect(() => {
    setOutputSize(current => current.format === format ? current : outputSizeFor(format));
  }, [format]);

  useEffect(() => {
    const available = (project?.brand_context?.assets?.references || []).map((_url, index) => `brand-reference-${index}`);
    setSelectedGlobalReferences(current => current.length ? current.filter(id => available.includes(id)) : available);
  }, [project?.id]);

  useEffect(() => {
    let active = true;
    setShelfLoading(true);
    const normalize = item => {
      const url = item.asset_url || item.image_url || item.thumb_url || item.url;
      return url ? {id: item.id || url, name: item.title || item.name || 'Imagem do Studio', url, thumbUrl: item.thumb_url || url, status: 'draft', source: 'library'} : null;
    };
    const loadShelf = project?.id
      ? loadProjectCreationHistory({apiRoot: bootstrap.apiRoot, clientId, projectId: project.id}).then(data => (data.items || []).map(normalize).filter(Boolean))
      : loadStudioLibrary({apiRoot: bootstrap.apiRoot, clientId}).then(data => {
        if (data.client_id) setPersonalClientId(String(data.client_id));
        return (data.personal_assets || []).map(normalize).filter(Boolean);
      });
    const loadPrevious = clientId ? listStudioSessions({apiRoot: bootstrap.apiRoot, clientId, projectId: project?.id || ''}).then(data => {
      const sessions = (data.items || []).filter(item => String(item.id) !== String(studioSessionRef.current?.id || ''));
      if (active) setSessionHistory(data.items || []);
      const assets = sessions.flatMap(session => {
        const editor = session.metadata?.editor || {};
        const candidates = editor.versions?.length ? editor.versions : editor.current_asset ? [editor.current_asset] : [];
        return candidates.map(item => normalize({...item, title: item.name || session.title})).filter(Boolean);
      });
      return assets.filter((item, index) => assets.findIndex(other => other.url === item.url) === index);
    }) : Promise.resolve([]);
    Promise.allSettled([loadShelf, loadPrevious]).then(([shelfResult, previousResult]) => {
      if (!active) return;
      setLibraryAssets(shelfResult.status === 'fulfilled' ? shelfResult.value : []);
      setPreviousAssets(previousResult.status === 'fulfilled' ? previousResult.value : []);
      setShelfLoading(false);
    });
    return () => { active = false; };
  }, [bootstrap.apiRoot, clientId, project?.id, studioSession?.id]);

  useEffect(() => {
    const snapshot = JSON.stringify({mask, crop, references, selectedId, format, selectedGlobalReferences});
    if (!lastEditorSnapshot.current) { lastEditorSnapshot.current = snapshot; return; }
    if (snapshot === lastEditorSnapshot.current) return;
    if (restoringHistory.current) { restoringHistory.current = false; lastEditorSnapshot.current = snapshot; setHistoryState({undo: editorUndo.current.length > 0, redo: editorRedo.current.length > 0}); return; }
    editorUndo.current.push(lastEditorSnapshot.current);
    if (editorUndo.current.length > 40) editorUndo.current.shift();
    editorRedo.current = [];
    lastEditorSnapshot.current = snapshot;
    setHistoryState({undo: true, redo: false});
  }, [crop, format, mask, references, selectedGlobalReferences, selectedId]);

  useEffect(() => { const timer = window.setTimeout(() => localStorage.setItem(storageKey, JSON.stringify({asset, versions, selectedId, prompt, format, outputSize, quality, zoom, mask, crop, selectedGlobalReferences, agentMessages})), 450); return () => window.clearTimeout(timer); }, [asset, versions, selectedId, prompt, format, outputSize, quality, zoom, mask, crop, selectedGlobalReferences, agentMessages, storageKey]);
  useEffect(() => {
    if (!asset || !clientId || studioSessionRef.current?.status === 'finalized') { setStatus(studioSessionRef.current?.status === 'finalized' ? 'synced' : 'local'); return undefined; }
    let disposed = false;
    const editorState = {
      format, output_size: outputSize, selected_id: selectedId, mask_bounds: mask?.bounds || null, crop_bounds: crop?.bounds || null,
      current_asset: {id: asset.id, name: asset.name, url: String(asset.url || '').startsWith('data:') ? '' : asset.url},
      versions: versions.map(item => ({id: item.id, name: item.name, status: item.status, url: String(item.url || '').startsWith('data:') ? '' : item.url})),
      references: references.map(item => ({id: item.id, name: item.name, assetId: item.assetId || '', url: String(item.dataUrl || '').startsWith('data:') ? '' : item.dataUrl})).filter(item => item.url),
      director: {objective: director.objective || '', preserve: director.preserve || []}, estimate: estimate || {}, selected_global_references: selectedGlobalReferences, batch_progress: batchProgress, agent_messages: agentMessages.slice(-12),
    };
    const timer = window.setTimeout(async () => {
      setStatus('saving');
      try {
        let next = studioSessionRef.current;
        if (!next) next = await createStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, payload: {project_id: project?.id || undefined, title: asset.name || 'Mesa de edição', original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata: {editor: editorState}}});
        else {
          if (!next.project_id && project?.id) next = await attachStudioSessionProject({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: next.id, projectId: project.id});
          next = await saveStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: next.id, payload: {expected_revision: next.revision, title: asset.name || 'Mesa de edição', original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata: {editor: editorState}}});
        }
        studioSessionRef.current = next;
        if (!disposed) { setStudioSession(next); setStatus('synced'); }
      } catch (error) {
        if (!disposed) {
          setStatus('local');
          if (String(error.message || '').includes('outra aba')) { setConflictOpen(true); setNotice('Esta mesa foi alterada em outra aba. Escolha qual versão manter.'); } else setNotice(`Não foi possível sincronizar este rascunho: ${error.message || 'erro desconhecido'}`);
        }
      }
    }, 700);
    return () => { disposed = true; window.clearTimeout(timer); };
  }, [asset, agentMessages, batchProgress, bootstrap.apiRoot, bootstrap.csrf, clientId, crop?.bounds, director, estimate, format, mask?.bounds, outputSize, project?.id, prompt, references, selectedGlobalReferences, selectedId, versions]);
  useEffect(() => {
    const latest = versions.find(item => item.status === 'new' && /^https?:\/\//.test(String(item.url || '')));
    const session = studioSessionRef.current || studioSession;
    if (!latest || !session || recordedGenerations.current.has(latest.id)) return;
    recordedGenerations.current.add(latest.id);
    acceptStudioSessionAsset({
      apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: session.id, asset: latest, role: 'base',
      metadata: {origin: 'edit', format, width: outputSize.width, height: outputSize.height, quality},
    }).then(updated => { studioSessionRef.current = updated; setStudioSession(updated); setStatus('synced'); }).catch(() => recordedGenerations.current.delete(latest.id));
  }, [bootstrap.apiRoot, bootstrap.csrf, clientId, format, outputSize.height, outputSize.width, studioSession, versions]);
  useEffect(() => {
    const finishOnExit = () => {
      const session = studioSessionRef.current;
      if (!session || session.status === 'finalized') return;
      const editor = {format, output_size: outputSize, selected_id: selectedId, mask_bounds: mask?.bounds || null, crop_bounds: crop?.bounds || null, current_asset: asset ? {id: asset.id, name: asset.name, url: /^https?:\/\//.test(String(asset.url || '')) ? asset.url : ''} : null, versions: versions.map(item => ({id: item.id, name: item.name, status: item.status, url: /^https?:\/\//.test(String(item.url || '')) ? item.url : ''})).filter(item => item.url), director: {objective: director.objective || '', preserve: director.preserve || []}, selected_global_references: selectedGlobalReferences, finalize_when_ready: generating, active_seconds: Math.round((Date.now() - startedAt.current) / 1000), completion_specifications: {format, width: outputSize.width, height: outputSize.height, quality, extension: 'PNG', project_name: project?.name || ''}};
      finalizeStudioSessionOnExit({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: session.id, hasEdits: generating || versions.some(item => item.status === 'new'), save: {expected_revision: session.revision, title: asset?.name || session.title || 'Mesa de edição', original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata: {editor}}, activeSeconds: Math.round((Date.now() - startedAt.current) / 1000), specifications: {format, width: outputSize.width, height: outputSize.height, quality, extension: 'PNG', project_name: project?.name || ''}});
    };
    window.addEventListener('pagehide', finishOnExit);
    return () => window.removeEventListener('pagehide', finishOnExit);
  }, [asset, bootstrap.apiRoot, bootstrap.csrf, clientId, crop?.bounds, director, format, generating, mask?.bounds, outputSize, project?.name, prompt, selectedGlobalReferences, selectedId, versions]);
  useEffect(() => {
    if (!asset || !prompt.trim()) { setEstimate(null); return undefined; }
    const timer = window.setTimeout(() => {
      requestQuote({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, prompt, format, clientId, hasMask: Boolean(mask)}).then(quote => setEstimate(quote)).catch(() => setEstimate(null));
    }, 420);
    return () => window.clearTimeout(timer);
  }, [asset, bootstrap.apiRoot, bootstrap.csrf, clientId, format, mask, prompt]);
  const upload = useCallback(async event => {
    const file = event.target.files?.[0]; event.target.value = ''; if (!file) return;
    if (!file.type.startsWith('image/')) { setNotice('Escolha uma imagem PNG, JPG ou WebP.'); return; }
    const dataUrl = await readFile(file);
    let next = {id: makeId(), name: file.name || 'Original', url: dataUrl, dataUrl, status: 'draft'};
    setAsset(next); setVersions([next]); setSelectedId(next.id); setMask(null); setNotice('Peça pronta para editar.');
    const projectId = project?.id || bootstrap.projectId;
    if (!clientId) return;
    try {
      const saved = await uploadStudioAsset({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, projectId, file});
      next = {...next, assetId: saved.asset_id, url: saved.url, dataUrl: saved.url};
      setAsset(next); setVersions([next]); setNotice('Peça salva na biblioteca e pronta para editar.');
    } catch (error) { setNotice(error.message || 'A peça ficou disponível localmente, mas não foi salva na biblioteca.'); }
  }, [bootstrap.apiRoot, bootstrap.csrf, bootstrap.projectId, clientId, project?.id]);
  const addReference = useCallback(async event => {
    const files = Array.from(event.target.files || []).filter(file => file.type.startsWith('image/')).slice(0, 2); event.target.value = '';
    const projectId = project?.id || bootstrap.projectId;
    const next = await Promise.all(files.map(async file => {
      const local = {id: makeId(), name: file.name, dataUrl: await readFile(file)};
      if (!clientId) return local;
      try {
        const saved = await uploadStudioAsset({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, projectId, file});
        return {...local, id: saved.id || local.id, assetId: saved.asset_id, dataUrl: saved.url};
      } catch (_error) { return local; }
    }));
    setReferences(current => [...current, ...next].slice(0, 2));
  }, [bootstrap.apiRoot, bootstrap.csrf, bootstrap.projectId, clientId, project?.id]);
  useEffect(() => {
    const fileEvent = file => ({target: {files: [file], value: ''}});
    const useAsReference = event => addReference(fileEvent(event.detail?.file));
    const replaceWithNewPiece = async event => {
      const file = event.detail?.file;
      if (!file) return;
      setStatus('saving');
      try {
        const editor = {
          format, output_size: outputSize, selected_id: selectedId, mask_bounds: mask?.bounds || null, crop_bounds: crop?.bounds || null,
          current_asset: asset ? {id: asset.id, name: asset.name, url: String(asset.url || '').startsWith('data:') ? '' : asset.url} : null,
          versions: versions.map(item => ({id: item.id, name: item.name, status: item.status, url: String(item.url || '').startsWith('data:') ? '' : item.url})).filter(item => item.url),
          references: references.map(item => ({id: item.id, name: item.name, assetId: item.assetId || '', url: String(item.dataUrl || '').startsWith('data:') ? '' : item.dataUrl})).filter(item => item.url),
          director: {objective: director.objective || '', preserve: director.preserve || []}, selected_global_references: selectedGlobalReferences, batch_progress: batchProgress,
        };
        let current = studioSessionRef.current;
        if (asset && clientId && !current) current = await createStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, payload: {project_id: project?.id || undefined, title: asset.name || 'Mesa de edição', original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata: {editor}}});
        else if (current) current = await saveStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: current.id, payload: {expected_revision: current.revision, title: asset?.name || current.title || 'Mesa de edição', original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata: {editor}}});
        studioSessionRef.current = null; setStudioSession(null); setPrompt(''); setReferences([]); setCrop(null); setMask(null); setStatus('local');
        await upload(fileEvent(file));
        setNotice(current ? 'Rascunho salvo. Uma nova sessão foi iniciada com a nova peça.' : 'Nova peça iniciada em uma sessão separada.');
      } catch (error) { setStatus('local'); setNotice(error.message || 'Não foi possível salvar o rascunho antes de iniciar a nova peça.'); }
    };
    window.addEventListener('cadu:studio-drop-reference', useAsReference);
    window.addEventListener('cadu:studio-drop-replace', replaceWithNewPiece);
    return () => { window.removeEventListener('cadu:studio-drop-reference', useAsReference); window.removeEventListener('cadu:studio-drop-replace', replaceWithNewPiece); };
  }, [addReference, asset, batchProgress, bootstrap.apiRoot, bootstrap.csrf, clientId, crop?.bounds, director, format, mask?.bounds, outputSize, project?.id, prompt, references, selectedGlobalReferences, selectedId, upload, versions]);
  const selectVersion = id => { const version = versions.find(item => item.id === id); if (!version) return; setSelectedId(id); setAsset(version); };
  const selectShelfAsset = item => {
    const existing = versions.find(version => version.url === item.url);
    if (existing) { setAsset(existing); setSelectedId(existing.id); setNotice(`${item.name} aberta como base desta sessão.`); return; }
    const next = {...item, id: `shelf:${item.id || makeId()}`, dataUrl: item.url, status: 'draft'};
    setVersions(current => [next, ...current]);
    setAsset(next); setSelectedId(next.id); setMask(null); setCrop(null); setNotice(`${item.name} aberta como base desta sessão.`);
  };
  const restoreEditorSnapshot = serialized => {
    const snapshot = JSON.parse(serialized);
    restoringHistory.current = true;
    setMask(snapshot.mask || null); setCrop(snapshot.crop || null); setReferences(snapshot.references || []); setFormat(snapshot.format || '4:5'); setSelectedGlobalReferences(snapshot.selectedGlobalReferences || []);
    const version = versions.find(item => item.id === snapshot.selectedId);
    if (version) { setSelectedId(version.id); setAsset(version); }
  };
  const undo = () => {
    if (!editorUndo.current.length) return;
    editorRedo.current.push(lastEditorSnapshot.current);
    restoreEditorSnapshot(editorUndo.current.pop());
    setHistoryState({undo: editorUndo.current.length > 0, redo: true});
  };
  const redo = () => {
    if (!editorRedo.current.length) return;
    editorUndo.current.push(lastEditorSnapshot.current);
    restoreEditorSnapshot(editorRedo.current.pop());
    setHistoryState({undo: true, redo: editorRedo.current.length > 0});
  };
  const approve = async id => {
    const version = versions.find(item => item.id === id);
    if (!version) return;
    setVersions(current => current.map(item => item.id === id ? {...item, status: 'approved'} : item));
    const session = studioSessionRef.current || studioSession;
    if (!session || !version.url || String(version.url).startsWith('data:')) { setNotice('Versão aprovada nesta mesa. Ela será sincronizada quando estiver salva no Studio.'); return; }
    try {
      const updated = await acceptStudioSessionAsset({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: session.id, asset: version});
      studioSessionRef.current = updated; setStudioSession(updated); setStatus('synced'); setNotice('Versão aprovada e vinculada à sessão do Studio.');
    } catch (error) { setNotice(error.message || 'A aprovação ficou local e será tentada novamente ao finalizar.'); }
  };
  const setBase = async id => {
    const version = versions.find(item => item.id === id);
    if (!version) return;
    selectVersion(id);
    const session = studioSessionRef.current || studioSession;
    if (!session || !version.url || String(version.url).startsWith('data:')) { setNotice('Esta é a peça-base local. Ela será vinculada quando estiver salva no Studio.'); return; }
    try {
      const updated = await acceptStudioSessionAsset({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: session.id, asset: version, role: 'base'});
      studioSessionRef.current = updated; setStudioSession(updated); setNotice('Peça-base atualizada para os próximos desdobramentos.');
    } catch (error) { setNotice(error.message || 'Não foi possível definir esta peça como base.'); }
  };
  const runEdition = async instruction => {
    if (!asset) { fileInput.current?.click(); return; }
    const effectivePrompt = String(instruction || prompt).trim();
    if (!effectivePrompt || generating) return;
    setGenerating(true);
    setAgentMessages(current => [...current, {id: makeId(), role: 'user', text: effectivePrompt}, {id: makeId(), role: 'assistant', text: 'Preparando a nova versão…'}]);
    setNotice('Preparando a edição com sua instrução…');
    try {
      const data = await requestEdition({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, asset, prompt: effectivePrompt, director: {...director, instruction: makeDirectorInstruction(effectivePrompt, director)}, format, outputSize, quality, mask, crop, clientId, references, globalReferenceIds: selectedGlobalReferences, brand: project?.brand_context});
      if (data.noop || data.mode === 'noop') { setNotice(data.preview || 'Marque uma região ou detalhe o pedido.'); setAgentMessages(current => [...current.slice(0, -1), {id: makeId(), role: 'assistant', text: data.preview || 'Qual parte da peça você quer alterar?'}]); return; }
      const url = data.image_url || data.png_data_url;
      if (!url) throw new Error(data.preview || 'A geração não devolveu uma imagem.');
      const nextVersion = {id: makeId(), name: `V${versions.length + 1}`, url, dataUrl: url, status: 'new'};
      setVersions(current => [nextVersion, ...current]); setAsset(nextVersion); setSelectedId(nextVersion.id); setMask(null); setCrop(null);
      setAgentMessages(current => [...current.slice(0, -1), {id: makeId(), role: 'assistant', text: 'Criei uma nova versão. Você pode revisar no palco ou pedir outro ajuste.'}]);
      setNotice('Nova edição pronta para revisar.');
    } catch (error) {
      setAgentMessages(current => [...current.slice(0, -1), {id: makeId(), role: 'assistant', text: error.message || 'Não foi possível concluir esta edição.'}]);
      setNotice(error.message || 'Não foi possível gerar esta edição.');
    } finally { setGenerating(false); }
  };
  const generate = async () => {
    const instruction = prompt.trim();
    if (instruction.length < 8) {
      setAgentMessages(current => [...current, {id: makeId(), role: 'assistant', text: 'O que você quer mudar na peça? Por exemplo: fundo, texto, produto ou enquadramento.'}]);
      return;
    }
    await runEdition(instruction);
  };
  const removeBackground = async () => {
    await runEdition('Remova completamente o fundo da imagem e entregue o elemento principal recortado, preservando bordas, transparências, sombras naturais, proporções e identidade visual.');
  };
  const newSession = async () => {
    if (generating || status === 'saving') return;
    const current = studioSessionRef.current || studioSession;
    if (asset && clientId) {
      setStatus('saving');
      const editor = {
        format, output_size: outputSize, selected_id: selectedId, mask_bounds: mask?.bounds || null, crop_bounds: crop?.bounds || null,
        current_asset: {id: asset.id, name: asset.name, url: String(asset.url || '').startsWith('data:') ? '' : asset.url},
        versions: versions.map(item => ({id: item.id, name: item.name, status: item.status, url: String(item.url || '').startsWith('data:') ? '' : item.url})),
        references: references.map(item => ({id: item.id, name: item.name, assetId: item.assetId || '', url: String(item.dataUrl || '').startsWith('data:') ? '' : item.dataUrl})).filter(item => item.url),
        director: {objective: director.objective || '', preserve: director.preserve || []}, selected_global_references: selectedGlobalReferences, batch_progress: batchProgress, agent_messages: agentMessages.slice(-12),
      };
      try {
        let saved = current;
        if (!saved) saved = await createStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, payload: {project_id: project?.id || undefined, title: asset.name || 'Mesa de edição', original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata: {editor}}});
        else saved = await saveStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: saved.id, payload: {expected_revision: saved.revision, title: asset.name || saved.title || 'Mesa de edição', original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata: {editor}}});
        setSessionHistory(history => [saved, ...history.filter(item => String(item.id) !== String(saved.id))]);
      } catch (error) {
        setStatus('local'); setNotice(error.message || 'Não foi possível salvar esta sessão antes de criar outra.'); return;
      }
    }
    studioSessionRef.current = null; setStudioSession(null); setAsset(null); setVersions([]); setSelectedId(''); setPrompt(''); setMask(null); setCrop(null); setReferences([]); setAgentMessages([]); setBatchProgress(null); setNotice('Nova sessão pronta. Arraste uma peça para começar.'); setStatus('local'); setZoom(100); setQuality('draft'); editorUndo.current = []; editorRedo.current = []; lastEditorSnapshot.current = ''; setHistoryState({undo: false, redo: false});
  };
  const finalize = async () => {
    const session = studioSessionRef.current || studioSession;
    if (!session) { setNotice('Selecione um projeto para sincronizar e finalizar esta sessão.'); return; }
    if (!asset?.url || String(asset.url).startsWith('data:')) { setNotice('Gere uma versão no Studio antes de finalizar: a peça enviada ainda está apenas neste navegador.'); return; }
    try {
      setStatus('saving');
      const accepted = await acceptStudioSessionAsset({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: session.id, asset, metadata: {origin: 'edit', format, width: outputSize.width, height: outputSize.height, quality}});
      const result = await finalizeStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: session.id, activeSeconds: Math.round((Date.now() - startedAt.current) / 1000), specifications: {format, width: outputSize.width, height: outputSize.height, quality, extension: 'PNG', project_name: project?.name || ''}});
      studioSessionRef.current = result.session || accepted;
      setStudioSession(result.session || accepted); setStatus('synced');
      setNotice('Sessão finalizada e a peça aprovada foi preservada no histórico.');
    } catch (error) { setStatus('synced'); setNotice(error.message || 'Não foi possível finalizar esta sessão.'); }
  };
  const continueEditing = async () => {
    const session = studioSessionRef.current || studioSession;
    if (!session) return;
    try {
      const next = await continueStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, sessionId: session.id, title: `Continuação · ${asset?.name || 'Edição'}`});
      studioSessionRef.current = next; setStudioSession(next); setStatus('synced'); setNotice('Nova sessão aberta a partir da peça final.');
    } catch (error) { setNotice(error.message || 'Não foi possível continuar esta sessão.'); }
  };
  const queueExpansion = async ({count, formats, completed = 0, base: storedBase} = {}) => {
    const base = storedBase || selected || asset;
    if (!base || generating) return;
    setGenerating(true);
    queueControl.current = {pause: false, cancel: false};
    setBatchProgress({status: 'running', total: count, completed, formats, base});
    try {
      for (let index = completed; index < count; index += 1) {
        if (queueControl.current.cancel) { setBatchProgress({status: 'cancelled', total: count, completed: index, formats, base}); setNotice('Fila cancelada. As peças já geradas seguem na revisão.'); return; }
        if (queueControl.current.pause) { setBatchProgress({status: 'paused', total: count, completed: index, formats, base}); setNotice('Fila pausada. Retome quando quiser.'); return; }
        const targetFormat = formats[index % formats.length];
        setNotice(`Gerando peça ${index + 1} de ${count} em ${targetFormat}…`);
        setBatchProgress({status: 'running', total: count, completed: index, formats, base});
        const instruction = prompt.trim() || `Adapte este criativo para ${targetFormat}, preservando a marca, o produto e a hierarquia visual.`;
        const data = await requestEdition({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, asset: base, prompt: instruction, format: targetFormat, outputSize: outputSizeFor(targetFormat), mask: null, clientId, references: [], globalReferenceIds: selectedGlobalReferences, brand: project?.brand_context});
        const url = data.image_url || data.png_data_url;
        if (!url) throw new Error(data.preview || `A peça ${index + 1} não foi gerada.`);
        const next = {id: makeId(), name: `Desdobramento ${index + 1} · ${targetFormat}`, url, dataUrl: url, status: 'new'};
        setVersions(current => [next, ...current]);
        setBatchProgress({status: 'running', total: count, completed: index + 1, formats, base});
      }
      setBatchProgress({status: 'completed', total: count, completed: count, formats, base});
      setNotice(`${count} peças entraram na revisão, sempre derivadas da peça-base.`);
    } catch (error) { setBatchProgress(current => current ? {...current, status: 'failed', failedIndex: current.completed} : current); setNotice(error.message || 'A fila foi interrompida nesta peça. Retome para tentar novamente.'); }
    finally { setGenerating(false); }
  };
  const pauseQueue = () => { queueControl.current.pause = true; setNotice('A fila será pausada ao concluir a peça atual.'); };
  const cancelQueue = () => { queueControl.current.cancel = true; if (!generating && batchProgress) setBatchProgress(current => current ? {...current, status: 'cancelled'} : current); setNotice(generating ? 'A fila será cancelada ao concluir a peça atual.' : 'Fila cancelada.'); };
  const resumeQueue = () => { if (!batchProgress?.base || !batchProgress?.formats?.length) { setNotice('Não foi possível localizar a peça-base desta fila.'); return; } queueExpansion({count: batchProgress.total, formats: batchProgress.formats, completed: batchProgress.failedIndex ?? batchProgress.completed, base: batchProgress.base}); };
  const quoteExpansion = useCallback(async ({count, formats}) => {
    const instruction = prompt.trim() || 'Adaptar este criativo, preservando marca, produto e hierarquia visual.';
    const quotes = await Promise.all(formats.map(formatOption => requestQuote({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, prompt: instruction, format: formatOption, clientId, hasMask: false})));
    return quotes.reduce((total, quote, index) => total + (Number(quote.estimated_tokens || 0) * (Math.floor(count / formats.length) + (index < count % formats.length ? 1 : 0))), 0);
  }, [bootstrap.apiRoot, bootstrap.csrf, clientId, prompt]);
  const openHistory = async () => {
    setHistoryOpen(true);
    if (!clientId) return;
    try {
      const data = await listStudioSessions({apiRoot: bootstrap.apiRoot, clientId, projectId: project?.id || ''});
      setSessionHistory(data.items || []);
    } catch (_error) { setSessionHistory([]); }
  };
  const changeProject = async id => {
    const nextProject = projects.find(item => String(item.id) === String(id)) || null;
    const previousClientId = clientId;
    setProject(nextProject);
    setSelectedGlobalReferences([]);
    const session = studioSessionRef.current || studioSession;
    if (session?.project_id && !nextProject) {
      studioSessionRef.current = null;
      setStudioSession(null);
      setStatus('local');
      setNotice('Sessão pessoal iniciada sem perder a peça atual.');
      return;
    }
    if (session && nextProject?.id && String(session.project_id || '') !== String(nextProject.id)) {
      if (String(nextProject.client_id || '') !== String(previousClientId || '')) {
        studioSessionRef.current = null;
        setStudioSession(null);
        setStatus('local');
        setNotice(`Projeto alterado para ${nextProject.name}. Uma nova sessão será criada sem perder a peça atual.`);
        return;
      }
      try {
        const updated = await attachStudioSessionProject({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId: previousClientId, sessionId: session.id, projectId: nextProject.id});
        studioSessionRef.current = updated; setStudioSession(updated); setNotice(`Projeto alterado para ${nextProject.name}.`);
      } catch (error) { setNotice(error.message || 'Não foi possível vincular este projeto à sessão.'); }
    }
  };
  const restoreSession = async ident => {
    try {
      const next = await readStudioSession({apiRoot: bootstrap.apiRoot, clientId, sessionId: ident});
      const editor = next.metadata?.editor || {};
      const restoredVersions = (editor.versions || []).filter(item => item.url).map(item => ({...item, dataUrl: item.url}));
      const restoredAsset = restoredVersions.find(item => item.id === editor.selected_id) || restoredVersions[0] || null;
      if (!restoredAsset) throw new Error('Esta sessão ainda não tem uma peça recuperável.');
      studioSessionRef.current = next; setStudioSession(next); setVersions(restoredVersions); setAsset(restoredAsset); setSelectedId(restoredAsset.id);
      setPrompt(next.optimized_prompt || next.original_prompt || ''); setFormat(editor.format || '4:5'); setOutputSize(editor.output_size || outputSizeFor(editor.format || '4:5')); setMask(null); setCrop(editor.crop_bounds ? {bounds: editor.crop_bounds} : null); setReferences((editor.references || []).filter(item => item.url).map(item => ({...item, dataUrl: item.url}))); setDirector({open: false, objective: editor.director?.objective || '', preserve: editor.director?.preserve || ['identity', 'copy', 'layout']}); setSelectedGlobalReferences(editor.selected_global_references || []); setAgentMessages(editor.agent_messages || []); setBatchProgress(editor.batch_progress || null);
      setHistoryOpen(false); setStatus('synced'); setNotice('Sessão restaurada. Continue a edição de onde parou.');
    } catch (error) { setNotice(error.message || 'Não foi possível restaurar esta sessão.'); }
  };
  useEffect(() => {
    if (bootstrap.sessionId && !studioSessionRef.current) restoreSession(bootstrap.sessionId);
  // The shared URL is intentionally restored once; subsequent session changes
  // are owned by the editor rather than the query string.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootstrap.sessionId]);
  const resolveConflictWithRemote = async () => {
    const session = studioSessionRef.current || studioSession;
    if (!session) return;
    await restoreSession(session.id);
    setConflictOpen(false);
  };
  const duplicateLocalSession = async () => {
    if (!clientId) return;
    try {
      const metadata = {editor: {format, selected_id: selectedId, mask_bounds: mask?.bounds || null, crop_bounds: crop?.bounds || null, current_asset: asset ? {id: asset.id, name: asset.name, url: String(asset.url || '').startsWith('data:') ? '' : asset.url} : null, versions: versions.map(item => ({id: item.id, name: item.name, status: item.status, url: String(item.url || '').startsWith('data:') ? '' : item.url})).filter(item => item.url), references: references.map(item => ({id: item.id, name: item.name, assetId: item.assetId || '', url: String(item.dataUrl || '').startsWith('data:') ? '' : item.dataUrl})).filter(item => item.url), director: {objective: director.objective || '', preserve: director.preserve || []}, selected_global_references: selectedGlobalReferences, batch_progress: batchProgress}};
      const next = await createStudioSession({apiRoot: bootstrap.apiRoot, csrf: bootstrap.csrf, clientId, payload: {project_id: project?.id || undefined, title: `Cópia local · ${asset?.name || 'Mesa de edição'}`, original_prompt: prompt, optimized_prompt: prompt, prompt_language: 'pt-BR', prompt_version: 'studio-editor-v1', metadata}});
      studioSessionRef.current = next; setStudioSession(next); setConflictOpen(false); setStatus('synced'); setNotice('Sua mesa local foi duplicada em uma nova sessão.');
    } catch (error) { setNotice(error.message || 'Não foi possível duplicar esta mesa local.'); }
  };
  const links = bootstrap.links || {};
  const estimateLabel = estimate?.estimated_tokens ? `${Number(estimate.estimated_tokens).toLocaleString('pt-BR')} créditos` : prompt.trim() ? 'calculando custo…' : 'custo ao gerar';
  const readOnly = studioSession?.status === 'finalized';
  const composer = <StudioComposer value={prompt} onChange={setPrompt} director={director} onDirectorChange={setDirector} onGenerate={generate} onAttach={() => referenceInput.current?.click()} references={references} onRemoveReference={index => setReferences(current => current.filter((_, itemIndex) => itemIndex !== index))} mask={mask ? {...mask, onClear: () => { maskRef.current?.clear(); setMask(null); }} : null} format={format} generating={generating} disabled={!asset || readOnly} estimateLabel={estimateLabel} messages={agentMessages}/>;
  return <div className={`se-app ${readOnly ? 'is-read-only' : ''}`}><StudioTopbar links={links} projects={projects} project={project} onProjectChange={changeProject} bootstrap={bootstrap} sessionName={studioSession?.title || asset?.name || 'Nova sessão de edição'} onHistory={openHistory} onNewSession={newSession}/><div className="se-layout"><LeftRail versions={versions} selectedId={selectedId} filter={railFilter} onFilter={setRailFilter} onSelect={selectVersion} onApprove={approve} onSetBase={setBase} onUpload={() => fileInput.current?.click()} onNewSession={newSession} onHistory={openHistory} onRestoreSession={restoreSession} sessions={sessionHistory} activeSessionId={studioSession?.id || ''} readOnly={readOnly} libraryUrl={links.library} project={project} libraryAssets={libraryAssets} previousAssets={previousAssets} shelfLoading={shelfLoading} onSelectAsset={selectShelfAsset}/><main className="se-main"><CanvasWorkspace asset={asset} mode={mode} setMode={setMode} mask={mask} crop={crop} maskRef={maskRef} onMaskChange={setMask} onCropChange={setCrop} onUpload={() => fileInput.current?.click()} format={format} outputSize={outputSize} onOutputSizeChange={setOutputSize} zoom={zoom} onZoomChange={setZoom} quality={quality} onQualityChange={setQuality} onRemoveBackground={removeBackground} onUndo={undo} onRedo={redo} canUndo={historyState.undo} canRedo={historyState.redo}/>{notice && <div className="se-notice" role="status">{notice}<button type="button" onClick={() => setNotice('')} aria-label="Fechar aviso">×</button></div>}</main><BrandPanel format={format} setFormat={setFormat} status={status} project={project} selectedGlobalReferences={selectedGlobalReferences} onGlobalReferencesChange={setSelectedGlobalReferences} batchProgress={batchProgress} onPauseQueue={pauseQueue} onCancelQueue={cancelQueue} onResumeQueue={resumeQueue} readOnly={readOnly} onHistory={openHistory} onFinalize={finalize} onContinue={continueEditing} onExpand={() => setExpandOpen(true)} composer={composer}/></div><input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={upload}/><input ref={referenceInput} type="file" accept="image/png,image/jpeg,image/webp" hidden multiple onChange={addReference}/>{historyOpen && <StudioModal title="Sessões e versões" onClose={() => setHistoryOpen(false)}><div className="se-history-dialog"><p>{studioSession ? 'Sessão atual sincronizada com o Studio.' : 'Versões locais desta mesa.'}</p>{versions.map(item => <button type="button" key={item.id} onClick={() => { selectVersion(item.id); setHistoryOpen(false); }}><img src={item.url} alt=""/><span>{item.name}</span><small>{item.status === 'approved' ? 'Aprovada' : 'Em edição'}</small></button>)}{sessionHistory.length > 0 && <><p>Outras sessões</p>{sessionHistory.filter(item => item.id !== studioSession?.id).map(item => <button type="button" className="se-history-session" key={item.id} onClick={() => restoreSession(item.id)}><span>{item.title || 'Mesa sem título'}</span><small>{item.status === 'finalized' ? 'Finalizada' : 'Em andamento'}</small></button>)}</>}</div></StudioModal>}{conflictOpen && <StudioModal title="Alteração em outra aba" onClose={() => setConflictOpen(false)}><div className="se-conflict-dialog"><p>Esta sessão foi atualizada em outra aba antes do seu último salvamento. Escolha a versão que deve continuar.</p><button type="button" onClick={resolveConflictWithRemote}><strong>Restaurar versão do Studio</strong><span>Descarta alterações desta aba e abre a última versão sincronizada.</span></button><button type="button" onClick={duplicateLocalSession}><strong>Duplicar minha mesa local</strong><span>Preserva suas alterações em uma nova sessão independente.</span></button></div></StudioModal>}{expandOpen && <ExpandDialog asset={selected || asset} onQuote={quoteExpansion} onQueue={queueExpansion} onClose={() => setExpandOpen(false)}/>}</div>;
}
