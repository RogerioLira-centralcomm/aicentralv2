import React, {useCallback, useState} from 'react';

export function DockDropZone({children, onDropItem, label = 'Fixar na dock'}) {
  const [active, setActive] = useState(false);
  const drop = useCallback(event => {
    event.preventDefault(); setActive(false);
    const raw = event.dataTransfer.getData('application/x-cadu-item');
    if (!raw) return;
    try { onDropItem?.(JSON.parse(raw)); } catch (_) { /* Ignore data from another application. */ }
  }, [onDropItem]);
  return <div className={`cadu-ds-dock-drop ${active ? 'is-active' : ''}`} onDragEnter={() => setActive(true)} onDragLeave={() => setActive(false)} onDragOver={event => event.preventDefault()} onDrop={drop} aria-label={label}>{children}</div>;
}

export function DockBrandShortcut({brand, projectCount = 0, active = false, onOpen, onDragStart}) {
  if (!brand.logoUrl) return null;
  return <button type="button" draggable onDragStart={event => onDragStart?.(event, {type: 'brand', id: brand.id, brandRef: brand.id})} onClick={() => onOpen?.(brand)} aria-label={`Abrir marca ${brand.name}`} className={`cadu-ds-dock-brand ${active ? 'is-active' : ''}`}>
    <img src={brand.logoUrl} alt=""/>
    {projectCount > 1 && <i aria-label={`${projectCount} projetos fixados`}>{projectCount}</i>}
  </button>;
}

export function DockResourceShortcut({item, pinned = false, onOpen, onDragStart}) {
  return <button type="button" draggable onDragStart={event => onDragStart?.(event, {type: item.kind, id: item.id, brandRef: item.brandRef, projectRef: item.projectRef})} onClick={() => onOpen?.(item)} aria-label={`Abrir ${item.title}`} className="cadu-ds-dock-resource">
    {item.previewUrl ? <img src={item.previewUrl} alt=""/> : <span aria-hidden="true">▤</span>}{pinned && <i aria-label="Fixado">●</i>}
  </button>;
}

export function DockUsageRing({percent, onOpen}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  return <button type="button" className="cadu-ds-usage-ring" style={{'--cadu-usage': `${value * 3.6}deg`}} onClick={onOpen} title="Utilização de créditos" aria-label={`Utilização de créditos: ${value}%`}><span>{value}%</span></button>;
}

export function CaduDock({logo, onHome, onNewConversation, brands = [], resources = [], shortcutItems = [], usagePercent, userAvatar, userInitials = 'C', onOpenBrand, onOpenResource, onDropItem, onOpenUsage}) {
  const writePayload = (event, payload) => { event.dataTransfer.effectAllowed = 'copy'; event.dataTransfer.setData('application/x-cadu-item', JSON.stringify(payload)); };
  const items = shortcutItems.length ? shortcutItems : [...brands, ...resources];
  const dockBrands = items.filter(item => item.kind === 'brand' && item.logoUrl);
  const dockResources = items.filter(item => item.kind !== 'brand');
  return <aside className="cadu-ds-dock" aria-label="Atalhos do Workspace">
    <button type="button" className="cadu-ds-dock-mark" onClick={onHome} aria-label="Ir para início">{logo ? <img src={logo} alt=""/> : '❮❮'}</button>
    <button type="button" className="cadu-ds-dock-new" onClick={onNewConversation} aria-label="Nova conversa">+</button>
    <DockDropZone onDropItem={onDropItem}>{dockBrands.map(item => <DockBrandShortcut key={item.shortcutId || item.id} brand={item} projectCount={item.projectCount} active={item.active} onOpen={onOpenBrand} onDragStart={writePayload}/>)}</DockDropZone>
    <div className="cadu-ds-dock-resources">{dockResources.slice(0, 8).map(item => <DockResourceShortcut key={item.shortcutId || item.id} item={item} pinned={item.pinned} onOpen={onOpenResource} onDragStart={writePayload}/>)}</div>
    <div className="cadu-ds-dock-bottom"><DockUsageRing percent={usagePercent} onOpen={onOpenUsage}/><button type="button" className="cadu-ds-dock-avatar-button" onClick={onOpenUsage} aria-label="Abrir conta">{userAvatar ? <img className="cadu-ds-dock-avatar" src={userAvatar} alt=""/> : <span className="cadu-ds-dock-avatar cadu-ds-dock-avatar--fallback">{userInitials}</span>}</button></div>
  </aside>;
}
